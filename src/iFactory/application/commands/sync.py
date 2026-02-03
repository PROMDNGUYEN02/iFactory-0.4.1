# File: application/commands/sync.py
"""
Sync Commands - With Remote ID Mapping Support.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


# =============================================================================
# ID Mapper Protocol
# =============================================================================


class IDeviceIdMapper(Protocol):
    """Protocol for device ID mapping (display <-> remote)."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        """Convert display IDs to remote IDs."""
        ...

    def to_display_id(self, remote_id: str) -> str:
        """Convert remote ID to display ID."""
        ...

    def to_remote_id(self, display_id: str) -> str:
        """Convert display ID to remote ID."""
        ...


class NoOpIdMapper:
    """Default mapper that returns IDs unchanged."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        return display_ids

    def to_display_id(self, remote_id: str) -> str:
        return remote_id

    def to_remote_id(self, display_id: str) -> str:
        return display_id


# =============================================================================
# Command Data Classes (Explicit Arguments)
# =============================================================================


@dataclass(frozen=True)
class SyncLatestStatusRequest:
    """Request to sync latest status for specified devices."""

    device_ids: List[str]
    """Explicit list of DISPLAY equipment codes to sync. Empty list = no-op."""


@dataclass(frozen=True)
class SyncHistoryRequest:
    """Request to sync history for specified devices within a time range."""

    device_ids: List[str]
    """Explicit list of DISPLAY equipment codes to sync."""

    start_time: datetime
    """Start of time range (inclusive)."""

    end_time: datetime
    """End of time range (inclusive)."""


@dataclass(frozen=True)
class SyncIncrementalRequest:
    """Request to sync recent history records for specified devices."""

    device_ids: List[str]
    """Explicit list of DISPLAY equipment codes to sync."""

    record_limit: int = 2
    """Number of recent records to fetch per device."""


# =============================================================================
# Response Data Classes
# =============================================================================


@dataclass
class SyncedDeviceData:
    """Data transfer object for a synced device."""

    equip_code: str  # Display ID (e.g., ALS01)
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

    Supports mapping between display IDs (UI) and remote IDs (database).
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()

    async def execute(self, request: SyncLatestStatusRequest) -> SyncLatestStatusResult:
        """
        Execute sync for the specified devices.

        Args:
            request: Contains explicit device_ids (DISPLAY IDs) to sync.

        Returns:
            SyncLatestStatusResult with synced device data (using DISPLAY IDs).
        """
        if not request.device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        # Step 1: Convert display IDs to remote IDs for fetching
        remote_ids = self._id_mapper.to_remote_ids(request.device_ids)

        logger.debug(f"[SyncLatestStatus] Fetching remote IDs: {remote_ids}")

        # Step 2: Fetch remote data using REMOTE IDs
        try:
            remote_records = await self._remote_source.fetch_latest_status(remote_ids)
        except Exception as e:
            logger.error(f"[SyncLatestStatus] Remote fetch failed: {e}")
            return SyncLatestStatusResult(error=str(e))

        if not remote_records:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        synced_devices: Dict[str, SyncedDeviceData] = {}

        async with self._uow_factory() as uow:
            # Pre-load ALL existing devices in ONE query
            existing_devices_dict: Dict[str, Device] = {}
            if uow.devices:
                try:
                    all_devices = await uow.devices.get_all()
                    existing_devices_dict = {device.equipment_code.value.upper(): device for device in all_devices}
                    logger.debug(f"[SyncLatestStatus] Pre-loaded {len(existing_devices_dict)} existing devices")
                except Exception as e:
                    logger.warning(f"[SyncLatestStatus] Failed to pre-load devices: {e}")

            devices_to_save: List[Device] = []

            for record in remote_records:
                try:
                    # Process record with ID mapping
                    device = self._process_record(record, existing_devices_dict)
                    if device:
                        devices_to_save.append(device)

                        # Use DISPLAY ID as the key in result
                        display_id = device.equipment_code.value
                        synced_devices[display_id] = SyncedDeviceData(
                            equip_code=display_id,
                            status_code=str(device.current_status.value),
                            status_name=device.current_status.name,
                            last_update=device.last_updated_at,
                            equip_name=device.equip_name,
                            is_active=device.is_active,
                        )
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"[SyncLatestStatus] Error processing {code}: {e}")

            # Bulk save all modified devices
            if uow.devices and devices_to_save:
                try:
                    if hasattr(uow.devices, "bulk_save"):
                        await uow.devices.bulk_save(devices_to_save)
                    else:
                        for device in devices_to_save:
                            await uow.devices.save(device)
                except Exception as e:
                    logger.error(f"[SyncLatestStatus] Bulk save failed: {e}")

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

        Converts remote_id from database to display_id for internal use.
        """
        # Get remote code from database
        remote_code = str(record.get("equip_code", "")).strip()
        if not remote_code:
            return None

        # *** KEY CHANGE: Convert remote_id to display_id ***
        display_code = self._id_mapper.to_display_id(remote_code)

        logger.debug(f"[SyncLatestStatus] Mapping: {remote_code} -> {display_code}")

        raw_status = record.get("raw_status") or record.get("equip_status") or "0"
        timestamp = record.get("last_update") or datetime.now()
        equip_name = record.get("equip_name")
        reason_code = record.get("reason_code")

        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        # Use DISPLAY code for lookup and storage
        code_upper = display_code.upper()
        existing_device = existing_devices.get(code_upper)

        if existing_device:
            updated = existing_device.sync_status(status_enum, timestamp)
            if updated:
                existing_device.update_remote_info(equip_name, reason_code)
                return existing_device
            else:
                logger.debug(f"[SyncLatestStatus] Stale data ignored for {display_code}")
                return None
        else:
            # Create new device with DISPLAY code
            code_vo = EquipmentCode(display_code)
            device = Device(
                equipment_code=code_vo,
                current_status=status_enum,
                last_updated_at=timestamp,
                equip_name=equip_name,
                reason_code=reason_code,
            )
            existing_devices[code_upper] = device
            return device


class SyncHistoryHandler:
    """
    Handler: Sync history for a time range.

    Supports mapping between display IDs (UI) and remote IDs (database).
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()

    async def execute(self, request: SyncHistoryRequest) -> SyncHistoryResult:
        """Execute history sync for the specified devices and time range."""
        if not request.device_ids:
            return SyncHistoryResult()

        total_synced = 0
        devices_processed = 0

        all_periods: List[StatusPeriod] = []
        equip_names: Dict[str, str] = {}

        try:
            # Fetch all remote data first
            device_records: Dict[str, List[Dict[str, Any]]] = {}

            for display_id in request.device_ids:
                # Convert to remote ID for fetching
                remote_id = self._id_mapper.to_remote_id(display_id)

                try:
                    records = await self._remote_source.fetch_device_history_range(remote_id, request.start_time, request.end_time)
                    if records:
                        # Store with display_id as key
                        device_records[display_id] = records
                except Exception as e:
                    logger.warning(f"[SyncHistory] Remote fetch failed for {display_id}: {e}")

            async with self._uow_factory() as uow:
                if not uow.history:
                    logger.warning("[SyncHistory] No history repository available")
                    return SyncHistoryResult(error="No history repository")

                for display_id, records in device_records.items():
                    # Use DISPLAY ID for periods
                    periods, equip_name = self._convert_to_periods(display_id, records)
                    if periods:
                        all_periods.extend(periods)
                        if equip_name:
                            equip_names[display_id] = equip_name
                        total_synced += len(periods)
                        devices_processed += 1

                if all_periods:
                    await uow.history.bulk_save_status_history(all_periods, equip_name=next(iter(equip_names.values()), None))

                await uow.commit()

        except Exception as e:
            logger.error(f"[SyncHistory] Transaction failed: {e}")
            return SyncHistoryResult(error=str(e))

        logger.info(f"[SyncHistory] Synced {total_synced} records for {devices_processed} devices")

        return SyncHistoryResult(
            records_synced=total_synced,
            devices_processed=devices_processed,
        )

    def _convert_to_periods(self, display_code: str, records: List[Dict[str, Any]]) -> tuple[List[StatusPeriod], Optional[str]]:  # Use display ID
        """Convert raw records to StatusPeriod value objects using display ID."""
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

            # Use DISPLAY code for the period
            period = StatusPeriod(
                equipment_code=EquipmentCode(display_code),
                status=status_enum,
                time_range=TimeRange(start=start_time, end=end_time),
            )
            periods.append(period)

        return periods, equip_name


class SyncIncrementalHistoryHandler:
    """
    Handler: Sync recent history records for upsert.

    Supports mapping between display IDs (UI) and remote IDs (database).
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()

    async def execute(self, request: SyncIncrementalRequest) -> SyncHistoryResult:
        """Execute incremental history sync."""
        if not request.device_ids:
            return SyncHistoryResult()

        total_updated = 0
        devices_processed = 0

        all_periods: List[StatusPeriod] = []
        equip_names: Dict[str, str] = {}

        try:
            device_records: Dict[str, List[Dict[str, Any]]] = {}

            for display_id in request.device_ids:
                # Convert to remote ID for fetching
                remote_id = self._id_mapper.to_remote_id(display_id)

                try:
                    records = await self._remote_source.fetch_latest_history_records(remote_id, limit=request.record_limit)
                    if records:
                        device_records[display_id] = records
                except Exception as e:
                    logger.debug(f"[SyncIncremental] Remote fetch failed for {display_id}: {e}")

            async with self._uow_factory() as uow:
                if not uow.history:
                    return SyncHistoryResult(error="No history repository")

                for display_id, records in device_records.items():
                    periods, equip_name = self._convert_to_periods(display_id, records)
                    if periods:
                        all_periods.extend(periods)
                        if equip_name:
                            equip_names[display_id] = equip_name
                        total_updated += len(periods)
                        devices_processed += 1

                if all_periods:
                    if hasattr(uow.history, "bulk_upsert_status_periods"):
                        await uow.history.bulk_upsert_status_periods(all_periods)
                    else:
                        for period in all_periods:
                            equip_name = equip_names.get(period.equipment_code.value)
                            await uow.history.save_status_period(period, equip_name=equip_name)

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

    def _convert_to_periods(self, display_code: str, records: List[Dict[str, Any]]) -> tuple[List[StatusPeriod], Optional[str]]:
        """Convert raw records to StatusPeriod value objects using display ID."""
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
                equipment_code=EquipmentCode(display_code),
                status=status_enum,
                time_range=TimeRange(start=start_time, end=end_time),
            )
            periods.append(period)

        return periods, equip_name


# =============================================================================
# Legacy Compatibility Wrappers (Updated with mapper support)
# =============================================================================


class SyncLatestStatusCommand:
    """DEPRECATED: Use SyncLatestStatusHandler with SyncLatestStatusRequest."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._handler = SyncLatestStatusHandler(remote_source, dual_uow_factory, id_mapper)

    async def execute(self, equipment_codes: List[str]) -> Dict[str, Any]:
        request = SyncLatestStatusRequest(device_ids=equipment_codes)
        result = await self._handler.execute(request)

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
    """DEPRECATED: Use SyncHistoryHandler with SyncHistoryRequest."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._handler = SyncHistoryHandler(remote_source, dual_uow_factory, id_mapper)

    async def execute(
        self,
        equipment_codes: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
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
    """DEPRECATED: Use SyncIncrementalHistoryHandler with SyncIncrementalRequest."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._handler = SyncIncrementalHistoryHandler(remote_source, dual_uow_factory, id_mapper)

    async def execute(self, equipment_codes: List[str]) -> int:
        request = SyncIncrementalRequest(device_ids=equipment_codes)
        result = await self._handler.execute(request)
        return result.records_synced


class SyncAllDevicesCommand:
    """DEPRECATED: Use SyncLatestStatusHandler directly."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._handler = SyncLatestStatusHandler(remote_source, dual_uow_factory, id_mapper)

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        request = SyncLatestStatusRequest(device_ids=equipment_codes or [])
        result = await self._handler.execute(request)
        return result.count


class SyncDeviceStatusCommand:
    """Handler: Sync history for a specific device (on-demand)."""

    def __init__(
        self,
        uow: AbstractUnitOfWork,
        remote_api: IRemoteDataSource,
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._uow = uow
        self._remote_api = remote_api
        self._id_mapper = id_mapper or NoOpIdMapper()

    async def execute(self, equip_code: str, days: int = 1) -> bool:
        """Sync history for a single device using display ID."""
        try:
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Convert display ID to remote ID for fetching
            remote_code = self._id_mapper.to_remote_id(equip_code)

            data = await self._remote_api.fetch_device_history_range(remote_code, start, now)

            if not data:
                return False

            equip_name = next((r.get("equip_name") for r in data if r.get("equip_name")), None)

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

                # Use DISPLAY code for the period
                period = StatusPeriod(
                    equipment_code=EquipmentCode(equip_code),  # Display ID
                    status=status_enum,
                    time_range=TimeRange(start=start_time, end=end_time),
                )
                periods.append(period)

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
    # Protocol
    "IDeviceIdMapper",
    "NoOpIdMapper",
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
