# File: application/services/sync_orchestrator.py
"""
Sync Orchestrator Service.
Coordinates sync operations for both Latest Status and History.
Optimized to sync only necessary devices based on current page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """
    Orchestrates all sync operations with optimized strategies:

    1. Latest Status Sync:
       - Only syncs devices visible on current page
       - Triggers immediate UI update after sync

    2. History Sync:
       - Initial load: 00:00 to now (once per app session)
       - Incremental: Every 3s, fetch last 2 records per device for upsert
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        on_sync_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory
        self._on_sync_complete = on_sync_complete

        # Track sync state
        self._initial_history_loaded: Set[str] = set()
        self._last_sync_time: Optional[datetime] = None
        self._current_page_devices: List[str] = []

        # Statistics
        self._stats = {
            "latest_synced": 0,
            "history_created": 0,
            "history_updated": 0,
        }

    def set_page_devices(self, device_codes: List[str]) -> None:
        """Update the list of devices for current page."""
        self._current_page_devices = device_codes
        logger.info(f"[SyncOrchestrator] Page devices updated: {len(device_codes)} devices")

    async def sync_latest_status(self, equipment_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sync latest status for specified devices (or current page devices).
        Returns dict with synced device data for immediate UI update.
        """
        codes_to_sync = equipment_codes or self._current_page_devices

        if not codes_to_sync:
            logger.debug("[SyncOrchestrator] No devices to sync for latest status")
            return {"devices": {}, "count": 0}

        try:
            # Fetch from remote
            remote_records = await self._remote_source.fetch_latest_status(codes_to_sync)

            if not remote_records:
                return {"devices": {}, "count": 0}

            synced_devices = {}

            async with self._uow_factory() as uow:
                for record in remote_records:
                    try:
                        device = await self._process_latest_record(uow, record)
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
                        logger.warning(f"[SyncOrchestrator] Error syncing {code}: {e}")

                await uow.commit()

            self._stats["latest_synced"] = len(synced_devices)
            self._last_sync_time = datetime.now()

            result = {
                "devices": synced_devices,
                "count": len(synced_devices),
                "timestamp": self._last_sync_time,
            }

            # Notify listeners
            if self._on_sync_complete:
                self._on_sync_complete(result)

            logger.info(f"[SyncOrchestrator] Latest status synced: {len(synced_devices)} devices")
            return result

        except Exception as e:
            logger.error(f"[SyncOrchestrator] Latest status sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

    async def sync_initial_history(self, equipment_codes: Optional[List[str]] = None) -> int:
        """
        Initial history sync: From 00:00 today to now.
        Only runs once per device per app session.
        """
        codes_to_sync = equipment_codes or self._current_page_devices

        # Filter out already loaded devices
        new_codes = [c for c in codes_to_sync if c not in self._initial_history_loaded]

        if not new_codes:
            logger.debug("[SyncOrchestrator] All devices already have initial history")
            return 0

        # Time range: 00:00 today to now
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_synced = 0

        try:
            async with self._uow_factory() as uow:
                for code in new_codes:
                    try:
                        records = await self._remote_source.fetch_device_history_range(code, start_of_day, now)

                        if records and uow.history:
                            count = await self._bulk_save_history(uow.history, code, records)
                            total_synced += count
                            self._initial_history_loaded.add(code)

                    except Exception as e:
                        logger.warning(f"[SyncOrchestrator] Initial history failed for {code}: {e}")

                await uow.commit()

            logger.info(f"[SyncOrchestrator] Initial history synced: {total_synced} records for {len(new_codes)} devices")
            return total_synced

        except Exception as e:
            logger.error(f"[SyncOrchestrator] Initial history sync failed: {e}")
            return 0

    async def sync_incremental_history(self, equipment_codes: Optional[List[str]] = None) -> int:
        """
        Incremental history sync: Fetch last 2 records per device for upsert.
        Runs every 3 seconds after initial load.
        """
        codes_to_sync = equipment_codes or self._current_page_devices

        if not codes_to_sync:
            return 0

        total_updated = 0

        try:
            async with self._uow_factory() as uow:
                for code in codes_to_sync:
                    try:
                        # Fetch only last 2 records
                        records = await self._remote_source.fetch_latest_history_records(code, limit=2)

                        if records and uow.history:
                            count = await self._upsert_history(uow.history, code, records)
                            total_updated += count

                    except Exception as e:
                        logger.debug(f"[SyncOrchestrator] Incremental sync failed for {code}: {e}")

                await uow.commit()

            if total_updated > 0:
                logger.debug(f"[SyncOrchestrator] Incremental history: {total_updated} records updated")

            return total_updated

        except Exception as e:
            logger.error(f"[SyncOrchestrator] Incremental history sync failed: {e}")
            return 0

    async def sync_all(self, equipment_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Combined sync: Latest status + History (initial or incremental).
        """
        codes = equipment_codes or self._current_page_devices

        # Sync latest status
        latest_result = await self.sync_latest_status(codes)

        # Sync history
        new_codes = [c for c in codes if c not in self._initial_history_loaded]

        if new_codes:
            # Initial load for new devices
            await self.sync_initial_history(new_codes)
        else:
            # Incremental for already loaded
            await self.sync_incremental_history(codes)

        return latest_result

    async def _process_latest_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> Optional[Device]:
        """Process a single latest status record."""
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

    async def _bulk_save_history(self, history_repo, equip_code: str, records: List[Dict[str, Any]]) -> int:
        """Bulk save history records."""
        if not records:
            return 0

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

    async def _upsert_history(self, history_repo, equip_code: str, records: List[Dict[str, Any]]) -> int:
        """Upsert history records (update or insert)."""
        if not records:
            return 0

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

            # Use save_status_period which does upsert via merge
            await history_repo.save_status_period(period, equip_name=equip_name)
            count += 1

        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            **self._stats,
            "last_sync": self._last_sync_time,
            "initial_loaded_count": len(self._initial_history_loaded),
            "current_page_devices": len(self._current_page_devices),
        }


__all__ = ["SyncOrchestrator"]
