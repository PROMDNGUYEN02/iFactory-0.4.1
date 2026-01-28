"""
Sync Devices Use Cases.
Handles synchronization logic for single and multiple devices.
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Syncs all (or specific) devices from Remote Source.
    Updates Hot Storage (Current State) and Cold Storage (History) via UoW.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"Failed to fetch from remote source: {e}")
            return 0

        if not remote_records:
            return 0

        count = 0
        async with self._uow_factory() as uow:
            for record in remote_records:
                try:
                    await self._process_record(uow, record)
                    count += 1
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"Error syncing device {code}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Synchronized {count} devices.")
        return count

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> None:
        # 1. Parse Data
        raw_code = str(record.get("equip_code"))
        raw_status = record.get("raw_status", "0")
        timestamp = record.get("last_update") or datetime.now()

        code_vo = EquipmentCode(raw_code)
        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        # 2. Update Hot Storage (Device Entity)
        device = Device(
            equipment_code=code_vo,
            current_status=status_enum,
            last_updated_at=timestamp,
            name=record.get("name"),
            description=record.get("description"),
        )
        await uow.devices.save(device)

        # 3. Update Cold Storage (History)
        # We rely on UoW to provide the history repository
        if uow.history:
            await self._update_history(uow.history, code_vo, status_enum, timestamp)

    async def _update_history(self, history_repo, code: EquipmentCode, new_status: MachineStatus, timestamp: datetime) -> None:
        """Ensures history continuity: Close old period, Open new period."""
        latest_period: Optional[StatusPeriod] = await history_repo.get_latest_status(code)

        # Case 1: No history -> Start new
        if not latest_period:
            new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange.starting_from(timestamp))
            await history_repo.save_status_period(new_period)
            return

        # Case 2: Status changed -> Close old, Start new
        if latest_period.status != new_status:
            closed_period = latest_period.with_end_time(timestamp)
            await history_repo.save_status_period(closed_period)

            new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange.starting_from(timestamp))
            await history_repo.save_status_period(new_period)


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs a single device status.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str) -> bool:
        try:
            data = await self._remote_api.fetch_device_status(equip_code)
            if not data:
                return False

            status_enum = MachineStatus.UNKNOWN
            try:
                status_enum = MachineStatus(int(data.get("equip_status", "0")))
            except (ValueError, TypeError):
                pass

            device = Device(
                equipment_code=EquipmentCode(data.get("equip_code")),
                current_status=status_enum,
                last_updated_at=data.get("last_update") or datetime.now(),
            )

            async with self._uow as uow:
                await uow.devices.save(device)
                await uow.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to sync device {equip_code}: {e}")
            return False
