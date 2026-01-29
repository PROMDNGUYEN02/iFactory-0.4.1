"""
Sync Devices Use Cases.
Handles synchronization logic for single and multiple devices.
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any, Union

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


async def _update_history_logic(
    history_repo,
    code: EquipmentCode,
    new_status: MachineStatus,
    timestamp: datetime,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> None:
    """
    Core logic to update status history.
    Handles continuity and fixes Time Travel (Future vs Present) conflicts.
    """
    latest_period: Optional[StatusPeriod] = await history_repo.get_latest_status(code)
    effective_start = start_time if start_time else timestamp

    # Case 1: No history -> Start new
    if not latest_period:
        new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange(start=effective_start, end=end_time))
        await history_repo.save_status_period(new_period)
        return

    # Case 2: Status Changed -> Close old, Open new
    if latest_period.status != new_status:
        # Determine closing time for the old period
        closing_time = effective_start

        # FIX: Time Travel Check (Closing time < Start time)
        # If the new status starts BEFORE the old status ended (impossible in linear time),
        # we clamp the closing time to the start time of the old period (creating a 0-duration period)
        if closing_time < latest_period.time_range.start:
            logger.warning(
                f"Timeline conflict for {code.value}: "
                f"Closing ({closing_time}) < Start ({latest_period.time_range.start}). "
                f"Clamping closing time to Start time."
            )
            closing_time = latest_period.time_range.start

        # Close old period
        closed_period = latest_period.with_end_time(closing_time)
        await history_repo.save_status_period(closed_period)

        # Open new period
        # Ensure new period doesn't start before the old one closed
        new_period_start = max(effective_start, closing_time)
        new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange(start=new_period_start, end=end_time))
        await history_repo.save_status_period(new_period)

    # Case 3: Same Status, but Ended? (Remote provided END_TIME)
    elif end_time and latest_period.time_range.end is None:
        closing_time = end_time

        # FIX: Time Travel Check
        if closing_time < latest_period.time_range.start:
            logger.warning(f"Timeline conflict for {code.value}: " f"End ({closing_time}) < Start ({latest_period.time_range.start}). " f"Clamping.")
            closing_time = latest_period.time_range.start

        closed_period = latest_period.with_end_time(closing_time)
        await history_repo.save_status_period(closed_period)


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
                    # Log warning to avoid crashing the whole sync loop
                    logger.warning(f"Error syncing device {code}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Synchronized {count} devices.")
        return count

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> None:
        raw_code = str(record.get("equip_code"))
        raw_status = record.get("raw_status", "0")

        # LOGIC: last_update determined by Adapter (END_TIME or NOW)
        timestamp = record.get("last_update") or datetime.now()

        # Raw remote fields
        reason_code = record.get("reason_code")
        equip_name = record.get("equip_name")
        remote_start_time = record.get("start_time")
        remote_end_time = record.get("end_time")

        code_vo = EquipmentCode(raw_code)
        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        # 1. Update Hot Storage (Device Entity)
        device = Device(
            equipment_code=code_vo,
            current_status=status_enum,
            last_updated_at=timestamp,
            equip_name=equip_name,
            reason_code=reason_code,
        )
        await uow.devices.save(device)

        # 2. Update Cold Storage (History)
        if uow.history:
            await _update_history_logic(uow.history, code_vo, status_enum, timestamp, remote_start_time, remote_end_time)


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs a single device status.
    Uses generic update logic to support both single dict and list of history records.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str, days: int = 30) -> bool:
        try:
            # Fetch data (Can be Dict or List[Dict] depending on Adapter)
            data = await self._remote_api.fetch_device_status(equip_code, days=days)

            if not data:
                return False

            # Normalize to list
            records = data if isinstance(data, list) else [data]

            async with self._uow as uow:
                for record in records:
                    raw_status = record.get("equip_status", "0")
                    timestamp = record.get("last_update") or datetime.now()

                    status_enum = MachineStatus.UNKNOWN
                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except (ValueError, TypeError):
                        pass

                    code_vo = EquipmentCode(record.get("equip_code"))
                    start_time = record.get("start_time")
                    end_time = record.get("end_time")

                    # 1. Update Cold Storage (History)
                    if uow.history:
                        await _update_history_logic(uow.history, code_vo, status_enum, timestamp, start_time, end_time)

                    # 2. Update Hot Storage (Latest State) - Overwrite with latest
                    device = Device(
                        equipment_code=code_vo,
                        current_status=status_enum,
                        last_updated_at=timestamp,
                        equip_name=record.get("equip_name"),
                        reason_code=record.get("reason_code"),
                    )
                    await uow.devices.save(device)

                await uow.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to sync device {equip_code}: {e}")
            return False
