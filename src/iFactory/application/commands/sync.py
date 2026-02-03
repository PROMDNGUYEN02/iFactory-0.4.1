# File: application/commands/sync.py
"""
Sync Commands.

Pure Application Layer commands for device synchronization.
All commands accept explicit arguments - no implicit UI state.

OPTIMIZED:
- Eliminated N+1 query patterns
- Pre-loads devices in bulk for O(1) lookup
- Single commit per transaction
- Uses sync_status() for external state observation (no transition policy)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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


# =============================================================================
# Command Data Classes (Explicit Arguments)
# =============================================================================


@dataclass(frozen=True)
class SyncLatestStatusRequest:
    """Request to sync latest status for specified devices."""

    device_ids: List[str]
    """Explicit list of equipment codes to sync. Empty list = no-op."""


@dataclass(frozen=True)
class SyncHistoryRequest:
    """Request to sync history for specified devices within a time range."""

    device_ids: List[str]
    """Explicit list of equipment codes to sync."""

    start_time: datetime
    """Start of time range (inclusive)."""

    end_time: datetime
    """End of time range (inclusive)."""


@dataclass(frozen=True)
class SyncIncrementalRequest:
    """Request to sync recent history records for specified devices."""

    device_ids: List[str]
    """Explicit list of equipment codes to sync."""

    record_limit: int = 2
    """Number of recent records to fetch per device."""


# =============================================================================
# Response Data Classes
# =============================================================================


@dataclass
class SyncedDeviceData:
    """Data transfer object for a synced device."""

    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime]
    equip_name: Optional[str]
    is_active: bool


@dataclass
class SyncLatestStatusResult:
    """Result of a latest status sync operation."""

    devices: Dict[str, SyncedDeviceData] = field(default_factory=dict)
    count: int = 0
    timestamp: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class SyncHistoryResult:
    """Result of a history sync operation."""

    records_synced: int = 0
    devices_processed: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


# =============================================================================
# Command Handlers
# =============================================================================


class SyncLatestStatusHandler:
    """
    Handler: Sync latest status for explicitly specified devices.

    This handler is UI-agnostic. The caller (e.g., Orchestrator or Controller)
    is responsible for determining which device IDs to sync.

    OPTIMIZATION NOTES:
    - Pre-loads ALL existing devices in ONE query
    - Uses in-memory dict for O(1) lookup
    - Collects changes and bulk-saves at the end
    - Single commit outside all loops
    - Uses sync_status() for external state observation (bypasses transition policy)
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory

    async def execute(self, request: SyncLatestStatusRequest) -> SyncLatestStatusResult:
        """
        Execute sync for the specified devices.

        Args:
            request: Contains explicit device_ids to sync.

        Returns:
            SyncLatestStatusResult with synced device data.

        Flow:
            1. Fetch remote data (already optimized - one row per device)
            2. Load ALL local devices in ONE query
            3. Build in-memory lookup dict
            4. Process each remote record against local state
            5. Bulk save all modified devices
            6. Commit ONCE at the end
        """
        if not request.device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        # Step 1: Fetch remote data (single query returning latest per device)
        try:
            remote_records = await self._remote_source.fetch_latest_status(request.device_ids)
        except Exception as e:
            logger.error(f"[SyncLatestStatus] Remote fetch failed: {e}")
            return SyncLatestStatusResult(error=str(e))

        if not remote_records:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        synced_devices: Dict[str, SyncedDeviceData] = {}

        async with self._uow_factory() as uow:
            # Step 2: Pre-load ALL existing devices in ONE query
            existing_devices_dict: Dict[str, Device] = {}
            if uow.devices:
                try:
                    all_devices = await uow.devices.get_all()
                    # Step 3: Build O(1) lookup dictionary keyed by equipment code
                    existing_devices_dict = {device.equipment_code.value.upper(): device for device in all_devices}
                    logger.debug(f"[SyncLatestStatus] Pre-loaded {len(existing_devices_dict)} existing devices")
                except Exception as e:
                    logger.warning(f"[SyncLatestStatus] Failed to pre-load devices: {e}")

            # Step 4: Process all remote records in memory
            devices_to_save: List[Device] = []

            for record in remote_records:
                try:
                    device = self._process_record(record, existing_devices_dict)
                    if device:
                        devices_to_save.append(device)
                        synced_devices[device.equipment_code.value] = SyncedDeviceData(
                            equip_code=device.equipment_code.value,
                            status_code=str(device.current_status.value),
                            status_name=device.current_status.name,
                            last_update=device.last_updated_at,
                            equip_name=device.equip_name,
                            is_active=device.is_active,
                        )
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"[SyncLatestStatus] Error processing {code}: {e}")

            # Step 5: Bulk save all modified devices (single batch operation)
            if uow.devices and devices_to_save:
                try:
                    if hasattr(uow.devices, "bulk_save"):
                        await uow.devices.bulk_save(devices_to_save)
                    else:
                        for device in devices_to_save:
                            await uow.devices.save(device)
                except Exception as e:
                    logger.error(f"[SyncLatestStatus] Bulk save failed: {e}")

            # Step 6: Single commit OUTSIDE all loops
            await uow.commit()

        logger.info(f"[SyncLatestStatus] Synced {len(synced_devices)} devices")

        return SyncLatestStatusResult(
            devices=synced_devices,
            count=len(synced_devices),
            timestamp=datetime.now(),
        )

    def _process_record(self, record: Dict[str, Any], existing_devices: Dict[str, Device]) -> Optional[Device]:
        """
        Process a single status record.

        Uses existing device if found, otherwise creates a new device entity.
        Uses sync_status() which does NOT enforce transition policy since
        we are observing external state, not commanding a change.

        Args:
            record: Remote status record
            existing_devices: Pre-loaded device lookup dict

        Returns:
            Device entity (updated or new), or None if processing failed
        """
        raw_code = str(record.get("equip_code", "")).strip()
        if not raw_code:
            return None

        raw_status = record.get("raw_status") or record.get("equip_status") or "0"
        timestamp = record.get("last_update") or datetime.now()
        equip_name = record.get("equip_name")
        reason_code = record.get("reason_code")

        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        code_upper = raw_code.upper()
        existing_device = existing_devices.get(code_upper)

        if existing_device:
            # Update existing device using sync_status (no transition policy)
            # This is an observation of external state, not a command
            updated = existing_device.sync_status(status_enum, timestamp)
            if updated:
                existing_device.update_remote_info(equip_name, reason_code)
                return existing_device
            else:
                # Stale data was rejected by timestamp guard
                logger.debug(f"[SyncLatestStatus] Stale data ignored for {raw_code}")
                return None
        else:
            # Create new device
            code_vo = EquipmentCode(raw_code)
            device = Device(
                equipment_code=code_vo,
                current_status=status_enum,
                last_updated_at=timestamp,
                equip_name=equip_name,
                reason_code=reason_code,
            )
            # Add to lookup dict for potential future lookups in same batch
            existing_devices[code_upper] = device
            return device


class SyncHistoryHandler:
    """
    Handler: Sync history for a time range.

    Used for initial history load or on-demand history fetching.

    NOTE: Remote API calls per device are unavoidable here since the remote
    source doesn't support bulk history fetch. However, we still:
    - Use bulk_save for persistence
    - Single commit at the end
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory

    async def execute(self, request: SyncHistoryRequest) -> SyncHistoryResult:
        """
        Execute history sync for the specified devices and time range.

        Args:
            request: Contains device_ids and time range.

        Returns:
            SyncHistoryResult with count of synced records.
        """
        if not request.device_ids:
            return SyncHistoryResult()

        total_synced = 0
        devices_processed = 0

        # Collect all periods across all devices for bulk save
        all_periods: List[StatusPeriod] = []
        equip_names: Dict[str, str] = {}

        try:
            # Fetch all remote data first (outside UoW to minimize transaction time)
            device_records: Dict[str, List[Dict[str, Any]]] = {}
            for code in request.device_ids:
                try:
                    records = await self._remote_source.fetch_device_history_range(code, request.start_time, request.end_time)
                    if records:
                        device_records[code] = records
                except Exception as e:
                    logger.warning(f"[SyncHistory] Remote fetch failed for {code}: {e}")

            # Now process within UoW
            async with self._uow_factory() as uow:
                if not uow.history:
                    logger.warning("[SyncHistory] No history repository available")
                    return SyncHistoryResult(error="No history repository")

                for code, records in device_records.items():
                    periods, equip_name = self._convert_to_periods(code, records)
                    if periods:
                        all_periods.extend(periods)
                        if equip_name:
                            equip_names[code] = equip_name
                        total_synced += len(periods)
                        devices_processed += 1

                # Bulk save all periods in one operation
                if all_periods:
                    await uow.history.bulk_save_status_history(all_periods, equip_name=next(iter(equip_names.values()), None))

                # Single commit outside all loops
                await uow.commit()

        except Exception as e:
            logger.error(f"[SyncHistory] Transaction failed: {e}")
            return SyncHistoryResult(error=str(e))

        logger.info(f"[SyncHistory] Synced {total_synced} records for {devices_processed} devices")

        return SyncHistoryResult(
            records_synced=total_synced,
            devices_processed=devices_processed,
        )

    def _convert_to_periods(self, equip_code: str, records: List[Dict[str, Any]]) -> tuple[List[StatusPeriod], Optional[str]]:
        """Convert raw records to StatusPeriod value objects."""
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

        return periods, equip_name


class SyncIncrementalHistoryHandler:
    """
    Handler: Sync recent history records for upsert.

    Fetches a limited number of recent records per device for incremental updates.

    OPTIMIZATION: Collects all periods and performs bulk upsert at the end.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory

    async def execute(self, request: SyncIncrementalRequest) -> SyncHistoryResult:
        """
        Execute incremental history sync.

        Args:
            request: Contains device_ids and record limit.

        Returns:
            SyncHistoryResult with count of updated records.
        """
        if not request.device_ids:
            return SyncHistoryResult()

        total_updated = 0
        devices_processed = 0

        # Collect all periods for bulk operation
        all_periods: List[StatusPeriod] = []
        equip_names: Dict[str, str] = {}

        try:
            # Fetch all remote data first
            device_records: Dict[str, List[Dict[str, Any]]] = {}
            for code in request.device_ids:
                try:
                    records = await self._remote_source.fetch_latest_history_records(code, limit=request.record_limit)
                    if records:
                        device_records[code] = records
                except Exception as e:
                    logger.debug(f"[SyncIncremental] Remote fetch failed for {code}: {e}")

            async with self._uow_factory() as uow:
                if not uow.history:
                    return SyncHistoryResult(error="No history repository")

                for code, records in device_records.items():
                    periods, equip_name = self._convert_to_periods(code, records)
                    if periods:
                        all_periods.extend(periods)
                        if equip_name:
                            equip_names[code] = equip_name
                        total_updated += len(periods)
                        devices_processed += 1

                # Bulk upsert all periods
                if all_periods:
                    if hasattr(uow.history, "bulk_upsert_status_periods"):
                        await uow.history.bulk_upsert_status_periods(all_periods)
                    else:
                        for period in all_periods:
                            equip_name = equip_names.get(period.equipment_code.value)
                            await uow.history.save_status_period(period, equip_name=equip_name)

                # Single commit outside all loops
                await uow.commit()

        except Exception as e:
            logger.error(f"[SyncIncremental] Transaction failed: {e}")
            return SyncHistoryResult(error=str(e))

        if total_updated > 0:
            logger.debug(f"[SyncIncremental] Updated {total_updated} records")

        return SyncHistoryResult(
            records_synced=total_updated,
            devices_processed=devices_processed,
        )

    def _convert_to_periods(self, equip_code: str, records: List[Dict[str, Any]]) -> tuple[List[StatusPeriod], Optional[str]]:
        """Convert raw records to StatusPeriod value objects."""
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

        return periods, equip_name


# =============================================================================
# Legacy Compatibility Wrappers
# =============================================================================


class SyncLatestStatusCommand:
    """
    DEPRECATED: Use SyncLatestStatusHandler with SyncLatestStatusRequest.

    Kept for backward compatibility during migration.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._handler = SyncLatestStatusHandler(remote_source, dual_uow_factory)

    async def execute(self, equipment_codes: List[str]) -> Dict[str, Any]:
        """Legacy execute method."""
        request = SyncLatestStatusRequest(device_ids=equipment_codes)
        result = await self._handler.execute(request)

        # Convert to legacy dict format
        return {
            "devices": {
                k: {
                    "equip_code": v.equip_code,
                    "status_code": v.status_code,
                    "status_name": v.status_name,
                    "last_update": v.last_update,
                    "equip_name": v.equip_name,
                    "is_active": v.is_active,
                }
                for k, v in result.devices.items()
            },
            "count": result.count,
            "timestamp": result.timestamp,
            **({"error": result.error} if result.error else {}),
        }


class SyncInitialHistoryCommand:
    """
    DEPRECATED: Use SyncHistoryHandler with SyncHistoryRequest.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._handler = SyncHistoryHandler(remote_source, dual_uow_factory)

    async def execute(
        self,
        equipment_codes: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Legacy execute method."""
        now = datetime.now()
        start = start_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_time or now

        request = SyncHistoryRequest(
            device_ids=equipment_codes,
            start_time=start,
            end_time=end,
        )
        result = await self._handler.execute(request)
        return result.records_synced


class SyncIncrementalHistoryCommand:
    """
    DEPRECATED: Use SyncIncrementalHistoryHandler with SyncIncrementalRequest.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._handler = SyncIncrementalHistoryHandler(remote_source, dual_uow_factory)

    async def execute(self, equipment_codes: List[str]) -> int:
        """Legacy execute method."""
        request = SyncIncrementalRequest(device_ids=equipment_codes)
        result = await self._handler.execute(request)
        return result.records_synced


class SyncAllDevicesCommand:
    """
    DEPRECATED: Use SyncLatestStatusHandler directly.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._handler = SyncLatestStatusHandler(remote_source, dual_uow_factory)

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        request = SyncLatestStatusRequest(device_ids=equipment_codes or [])
        result = await self._handler.execute(request)
        return result.count


class SyncDeviceStatusCommand:
    """
    Handler: Sync history for a specific device (on-demand).

    Used for on-demand Gantt chart loading.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str, days: int = 1) -> bool:
        """Sync history for a single device."""
        try:
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            data = await self._remote_api.fetch_device_history_range(equip_code, start, now)

            if not data:
                return False

            equip_name = next((r.get("equip_name") for r in data if r.get("equip_name")), None)

            # Build all periods first
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

            # Single UoW usage with bulk save
            async with self._uow as uow:
                if uow.history and periods:
                    await uow.history.bulk_save_status_history(periods, equip_name=equip_name)
                await uow.commit()

            logger.info(f"[SyncDeviceStatus] Synced {len(data)} records for {equip_code}")
            return True

        except Exception as e:
            logger.error(f"[SyncDeviceStatus] Failed for {equip_code}: {e}")
            return False


__all__ = [
    # New API (Recommended)
    "SyncLatestStatusRequest",
    "SyncHistoryRequest",
    "SyncIncrementalRequest",
    "SyncLatestStatusResult",
    "SyncHistoryResult",
    "SyncedDeviceData",
    "SyncLatestStatusHandler",
    "SyncHistoryHandler",
    "SyncIncrementalHistoryHandler",
    # Legacy API (Deprecated)
    "SyncLatestStatusCommand",
    "SyncInitialHistoryCommand",
    "SyncIncrementalHistoryCommand",
    "SyncAllDevicesCommand",
    "SyncDeviceStatusCommand",
]
