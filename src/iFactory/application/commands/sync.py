# File: application/commands/sync.py
"""
Sync Commands.
Handles synchronization logic for devices and history.
Optimized for page-based syncing.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


class SyncLatestStatusCommand:
    """
    COMMAND: Sync latest status for specified devices only.
    Optimized: Only syncs devices visible on current page.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory

    async def execute(self, equipment_codes: List[str]) -> Dict[str, Any]:
        """
        Execute sync for specific devices.
        Returns dict of synced device data for immediate UI update.
        """
        if not equipment_codes:
            return {"devices": {}, "count": 0}

        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"[SyncLatestStatus] Failed to fetch from remote: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

        if not remote_records:
            return {"devices": {}, "count": 0}

        synced_devices = {}

        async with self._uow_factory() as uow:
            for record in remote_records:
                try:
                    device = await self._process_record(uow, record)
                    if device:
                        synced_devices[device.equipment_code.value] = {
                            "equip_code": device.equipment_code.value,
                            "status_code": str(device.current_status.value),
                            "status_name": device.current_status.name,
                            "last_update": device.last_updated_at,
                            "equip_name": device.equip_name,
                            "is_active": device.is_active,
                        }
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"[SyncLatestStatus] Error processing {code}: {e}")

            await uow.commit()

        logger.info(f"[SyncLatestStatus] Synced {len(synced_devices)} devices")
        return {
            "devices": synced_devices,
            "count": len(synced_devices),
            "timestamp": datetime.now(),
        }

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> Optional[Device]:
        """Process a single status record."""
        raw_code = str(record.get("equip_code"))
        raw_status = record.get("raw_status") or record.get("equip_status") or "0"
        timestamp = record.get("last_update") or datetime.now()
        equip_name = record.get("equip_name")
        reason_code = record.get("reason_code")

        code_vo = EquipmentCode(raw_code)

        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        device = Device(
            equipment_code=code_vo,
            current_status=status_enum,
            last_updated_at=timestamp,
            equip_name=equip_name,
            reason_code=reason_code,
        )

        if uow.devices:
            await uow.devices.save(device)

        return device


class SyncInitialHistoryCommand:
    """
    COMMAND: Sync history from 00:00 today to now.
    Runs once per device per app session.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory

    async def execute(
        self,
        equipment_codes: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Execute initial history sync.
        Default: From 00:00 today to now.
        """
        if not equipment_codes:
            return 0

        now = datetime.now()
        start = start_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_time or now

        total_synced = 0

        async with self._uow_factory() as uow:
            if not uow.history:
                logger.warning("[SyncInitialHistory] No history repository available")
                return 0

            for code in equipment_codes:
                try:
                    records = await self._remote_source.fetch_device_history_range(code, start, end)

                    if records:
                        count = await self._bulk_save(uow.history, code, records)
                        total_synced += count

                except Exception as e:
                    logger.warning(f"[SyncInitialHistory] Failed for {code}: {e}")

            await uow.commit()

        logger.info(f"[SyncInitialHistory] Synced {total_synced} history records")
        return total_synced

    async def _bulk_save(self, history_repo, equip_code: str, records: List[Dict[str, Any]]) -> int:
        """Bulk save history records."""
        periods = []
        equip_name = None

        for record in records:
            equip_name = equip_name or record.get("equip_name")
            start_time = record.get("start_time")

            if not start_time:
                continue

            raw_status = record.get("equip_status", "0")
            try:
                status_enum = MachineStatus(int(raw_status))
            except (ValueError, TypeError):
                status_enum = MachineStatus.UNKNOWN

            end_time = record.get("end_time")
            if end_time and end_time < start_time:
                end_time = start_time

            period = StatusPeriod(
                equipment_code=EquipmentCode(equip_code),
                status=status_enum,
                time_range=TimeRange(start=start_time, end=end_time),
            )
            periods.append(period)

        if periods:
            await history_repo.bulk_save_status_history(periods, equip_name=equip_name)

        return len(periods)


class SyncIncrementalHistoryCommand:
    """
    COMMAND: Sync last 2 records per device for upsert.
    Runs every 3 seconds after initial load.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory

    async def execute(self, equipment_codes: List[str]) -> int:
        """
        Execute incremental history sync.
        Fetches last 2 records per device to upsert.
        """
        if not equipment_codes:
            return 0

        total_updated = 0

        async with self._uow_factory() as uow:
            if not uow.history:
                return 0

            for code in equipment_codes:
                try:
                    # Fetch last 2 records only
                    records = await self._remote_source.fetch_latest_history_records(code, limit=2)

                    if records:
                        count = await self._upsert_records(uow.history, code, records)
                        total_updated += count

                except Exception as e:
                    logger.debug(f"[SyncIncrementalHistory] Failed for {code}: {e}")

            await uow.commit()

        if total_updated > 0:
            logger.debug(f"[SyncIncrementalHistory] Updated {total_updated} records")

        return total_updated

    async def _upsert_records(self, history_repo, equip_code: str, records: List[Dict[str, Any]]) -> int:
        """Upsert history records."""
        count = 0
        equip_name = None

        for record in records:
            equip_name = equip_name or record.get("equip_name")
            start_time = record.get("start_time")

            if not start_time:
                continue

            raw_status = record.get("equip_status", "0")
            try:
                status_enum = MachineStatus(int(raw_status))
            except (ValueError, TypeError):
                status_enum = MachineStatus.UNKNOWN

            end_time = record.get("end_time")
            if end_time and end_time < start_time:
                end_time = start_time

            period = StatusPeriod(
                equipment_code=EquipmentCode(equip_code),
                status=status_enum,
                time_range=TimeRange(start=start_time, end=end_time),
            )

            # save_status_period uses merge for upsert
            await history_repo.save_status_period(period, equip_name=equip_name)
            count += 1

        return count


# Legacy compatibility
class SyncAllDevicesCommand:
    """
    DEPRECATED: Use SyncLatestStatusCommand instead.
    Kept for backward compatibility.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._sync_cmd = SyncLatestStatusCommand(remote_source, dual_uow_factory)

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        result = await self._sync_cmd.execute(equipment_codes or [])
        return result.get("count", 0)


class SyncDeviceStatusCommand:
    """
    COMMAND: Sync history for a specific device.
    Used for on-demand Gantt chart loading.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str, days: int = 1) -> bool:
        try:
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            data = await self._remote_api.fetch_device_history_range(equip_code, start, now)

            if not data:
                return False

            equip_name = next((r.get("equip_name") for r in data if r.get("equip_name")), None)

            async with self._uow as uow:
                if uow.history:
                    periods = []
                    for record in data:
                        start_time = record.get("start_time")
                        if not start_time:
                            continue

                        raw_status = record.get("equip_status", "0")
                        try:
                            status_enum = MachineStatus(int(raw_status))
                        except (ValueError, TypeError):
                            status_enum = MachineStatus.UNKNOWN

                        end_time = record.get("end_time")
                        if end_time and end_time < start_time:
                            end_time = start_time

                        period = StatusPeriod(
                            equipment_code=EquipmentCode(record.get("equip_code")),
                            status=status_enum,
                            time_range=TimeRange(start=start_time, end=end_time),
                        )
                        periods.append(period)

                    if periods:
                        await uow.history.bulk_save_status_history(periods, equip_name=equip_name)

                await uow.commit()

            logger.info(f"[SyncDeviceStatus] Synced {len(data)} records for {equip_code}")
            return True

        except Exception as e:
            logger.error(f"[SyncDeviceStatus] Failed for {equip_code}: {e}")
            return False


__all__ = [
    "SyncLatestStatusCommand",
    "SyncInitialHistoryCommand",
    "SyncIncrementalHistoryCommand",
    "SyncAllDevicesCommand",
    "SyncDeviceStatusCommand",
]
