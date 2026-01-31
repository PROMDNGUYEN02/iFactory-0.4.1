# File: application/commands/sync.py
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
    COMMAND: Synchronizes snapshot status for all devices from remote source.
    Also updates historical status continuity based on snapshot changes.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory
        self._history_created = 0
        self._history_updated = 0

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"Failed to fetch from remote source: {e}")
            return 0

        if not remote_records:
            return 0

        count = 0
        self._history_created = 0
        self._history_updated = 0

        async with self._uow_factory() as uow:
            has_history = uow.history is not None
            if not has_history:
                logger.warning("DualUoW history repository is None! Check session factory.")

            for record in remote_records:
                try:
                    await self._process_record(uow, record)
                    count += 1
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"Error syncing device {code}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Synchronized {count} devices. History: +{self._history_created} created, {self._history_updated} updated")
        return count

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> None:
        raw_code = str(record.get("equip_code"))
        raw_status = record.get("raw_status") or record.get("equip_status") or "0"
        timestamp = record.get("last_update") or datetime.now()
        reason_code = record.get("reason_code")
        equip_name = record.get("equip_name")
        remote_start_time = record.get("start_time")
        remote_end_time = record.get("end_time")

        code_vo = EquipmentCode(raw_code)
        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        # Update Hot Store (Current Status)
        device = Device(
            equipment_code=code_vo,
            current_status=status_enum,
            last_updated_at=timestamp,
            equip_name=equip_name,
            reason_code=reason_code,
        )

        if uow.devices:
            await uow.devices.save(device)

        # Update Cold Store (History Continuity)
        if uow.history:
            await self._synchronize_history(
                uow.history,
                code_vo,
                status_enum,
                timestamp,
                remote_start_time,
                remote_end_time,
                equip_name=equip_name,
            )

    async def _synchronize_history(
        self,
        history_repo,
        code: EquipmentCode,
        new_status: MachineStatus,
        timestamp: datetime,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        equip_name: Optional[str] = None,
    ) -> None:
        """
        Maintain continuity of status periods based on snapshot updates.
        Always ensures at least one history record exists per device.
        """
        latest_period: Optional[StatusPeriod] = await history_repo.get_latest_status(code)

        # Use timestamp as start_time if not provided
        effective_start = start_time if start_time else timestamp

        if not latest_period:
            # First record for this device - ALWAYS create one
            actual_end = end_time
            if actual_end and actual_end < effective_start:
                actual_end = effective_start

            new_period = StatusPeriod(
                equipment_code=code,
                status=new_status,
                time_range=TimeRange(start=effective_start, end=actual_end),
            )
            await history_repo.save_status_period(new_period, equip_name=equip_name)
            self._history_created += 1
            return

        # Check if status changed
        if latest_period.status != new_status:
            # Close previous period
            closing_time = effective_start
            if closing_time < latest_period.time_range.start:
                closing_time = latest_period.time_range.start
            closed_period = latest_period.with_end_time(closing_time)
            await history_repo.save_status_period(closed_period, equip_name=equip_name)

            # Start new period
            new_period_start = max(effective_start, closing_time)
            actual_end = end_time
            if actual_end and actual_end < new_period_start:
                actual_end = new_period_start
            new_period = StatusPeriod(
                equipment_code=code,
                status=new_status,
                time_range=TimeRange(start=new_period_start, end=actual_end),
            )
            await history_repo.save_status_period(new_period, equip_name=equip_name)
            self._history_updated += 1

        elif latest_period.time_range.end is None:
            # Same status, period is open - update end time if we have one
            if end_time:
                closing_time = end_time
                if closing_time < latest_period.time_range.start:
                    closing_time = latest_period.time_range.start
                closed_period = latest_period.with_end_time(closing_time)
                await history_repo.save_status_period(closed_period, equip_name=equip_name)
                self._history_updated += 1


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs History for a specific device.
    OPTIMIZED: Bulk processing.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str, days: int = 30) -> bool:
        try:
            data = await self._remote_api.fetch_device_status(equip_code, days=days)
            if not data:
                return False

            records = data if isinstance(data, list) else [data]
            if not records:
                return True

            master_equip_name = next((r.get("equip_name") for r in records if r.get("equip_name")), None)

            batch_periods: List[StatusPeriod] = []
            latest_record = None
            latest_timestamp = datetime.min

            async with self._uow as uow:
                for record in records:
                    raw_status = record.get("equip_status", "0")
                    timestamp = record.get("last_update") or datetime.now()

                    if timestamp >= latest_timestamp:
                        latest_timestamp = timestamp
                        latest_record = record

                    start_time = record.get("start_time")
                    if start_time:
                        code_vo = EquipmentCode(record.get("equip_code"))
                        end_time = record.get("end_time")

                        try:
                            status_enum = MachineStatus(int(raw_status))
                        except (ValueError, TypeError):
                            status_enum = MachineStatus.UNKNOWN

                        actual_end = end_time if end_time else None
                        if actual_end and actual_end < start_time:
                            actual_end = start_time

                        period = StatusPeriod(
                            equipment_code=code_vo,
                            status=status_enum,
                            time_range=TimeRange(start=start_time, end=actual_end),
                        )
                        batch_periods.append(period)

                if uow.history and batch_periods:
                    await uow.history.bulk_save_status_history(batch_periods, equip_name=master_equip_name)

                if latest_record and uow.devices:
                    raw_status = latest_record.get("equip_status", "0")
                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except (ValueError, TypeError):
                        status_enum = MachineStatus.UNKNOWN

                    device = Device(
                        equipment_code=EquipmentCode(latest_record.get("equip_code")),
                        current_status=status_enum,
                        last_updated_at=latest_timestamp,
                        equip_name=master_equip_name,
                        reason_code=latest_record.get("reason_code"),
                    )
                    await uow.devices.save(device)

                await uow.commit()

            logger.info(f"Synced {len(batch_periods)} history records for {equip_code}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync device {equip_code}: {e}")
            return False


__all__ = ["SyncAllDevicesCommand", "SyncDeviceStatusCommand"]
