# File: application/commands/sync.py
"""
Sync Commands.

Pure Application Layer commands for device synchronization.
All commands accept explicit arguments - no implicit UI state.
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
        """
        if not request.device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        try:
            remote_records = await self._remote_source.fetch_latest_status(request.device_ids)
        except Exception as e:
            logger.error(f"[SyncLatestStatus] Remote fetch failed: {e}")
            return SyncLatestStatusResult(error=str(e))

        if not remote_records:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        synced_devices: Dict[str, SyncedDeviceData] = {}

        async with self._uow_factory() as uow:
            for record in remote_records:
                try:
                    device = await self._process_record(uow, record)
                    if device:
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

            await uow.commit()

        logger.info(f"[SyncLatestStatus] Synced {len(synced_devices)} devices")

        return SyncLatestStatusResult(
            devices=synced_devices,
            count=len(synced_devices),
            timestamp=datetime.now(),
        )

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> Optional[Device]:
        """Process a single status record into a Device entity."""
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


class SyncHistoryHandler:
    """
    Handler: Sync history for a time range.

    Used for initial history load or on-demand history fetching.
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

        try:
            async with self._uow_factory() as uow:
                if not uow.history:
                    logger.warning("[SyncHistory] No history repository available")
                    return SyncHistoryResult(error="No history repository")

                for code in request.device_ids:
                    try:
                        records = await self._remote_source.fetch_device_history_range(code, request.start_time, request.end_time)

                        if records:
                            count = await self._bulk_save(uow.history, code, records)
                            total_synced += count
                            devices_processed += 1

                    except Exception as e:
                        logger.warning(f"[SyncHistory] Failed for {code}: {e}")

                await uow.commit()

        except Exception as e:
            logger.error(f"[SyncHistory] Transaction failed: {e}")
            return SyncHistoryResult(error=str(e))

        logger.info(f"[SyncHistory] Synced {total_synced} records for {devices_processed} devices")

        return SyncHistoryResult(
            records_synced=total_synced,
            devices_processed=devices_processed,
        )

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


class SyncIncrementalHistoryHandler:
    """
    Handler: Sync recent history records for upsert.

    Fetches a limited number of recent records per device for incremental updates.
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

        try:
            async with self._uow_factory() as uow:
                if not uow.history:
                    return SyncHistoryResult(error="No history repository")

                for code in request.device_ids:
                    try:
                        records = await self._remote_source.fetch_latest_history_records(code, limit=request.record_limit)

                        if records:
                            count = await self._upsert_records(uow.history, code, records)
                            total_updated += count
                            devices_processed += 1

                    except Exception as e:
                        logger.debug(f"[SyncIncremental] Failed for {code}: {e}")

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

            await history_repo.save_status_period(period, equip_name=equip_name)
            count += 1

        return count


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
