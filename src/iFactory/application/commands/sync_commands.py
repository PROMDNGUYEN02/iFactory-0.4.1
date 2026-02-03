# src/application/commands/sync_commands.py
"""
Enhanced Sync Commands using Mediator pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from iFactory.shared.core.result import Result, Error, Errors
from iFactory.application.mediator import Request, IRequestHandler

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response DTOs
# ============================================================================


@dataclass(frozen=True)
class SyncedDevice:
    """Single synced device data."""

    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime]
    equip_name: Optional[str]
    is_active: bool


@dataclass(frozen=True)
class SyncLatestResponse:
    """Response from sync latest status."""

    devices: Dict[str, SyncedDevice]
    count: int
    timestamp: datetime

    @property
    def device_ids(self) -> List[str]:
        return list(self.devices.keys())


@dataclass(frozen=True)
class SyncHistoryResponse:
    """Response from sync history."""

    records_synced: int
    devices_processed: int


# ============================================================================
# Sync Latest Status Command
# ============================================================================


@dataclass(frozen=True)
class SyncLatestStatusCommand(Request[Result[SyncLatestResponse, Error]]):
    """
    Command to sync latest device status from remote source.

    Uses DISPLAY IDs (what UI shows) which get mapped to
    REMOTE IDs (what database uses) internally.
    """

    device_ids: tuple[str, ...]  # Immutable for hashing

    @classmethod
    def create(cls, device_ids: List[str]) -> "SyncLatestStatusCommand":
        """Factory method with list input."""
        return cls(device_ids=tuple(device_ids))

    @property
    def cache_key(self) -> str:
        """Cache key for this request."""
        ids_hash = hash(self.device_ids)
        return f"sync_latest:{ids_hash}"

    cache_ttl: int = 3  # Short cache for real-time data


class SyncLatestStatusHandler(IRequestHandler[Result[SyncLatestResponse, Error]]):
    """
    Handler for SyncLatestStatusCommand.

    Fetches latest status from remote source and updates local storage.
    """

    def __init__(
        self,
        remote_source,  # IRemoteDataSource
        uow_factory,  # Callable[[], AbstractUnitOfWork]
        id_mapper=None,  # IDeviceIdMapper
    ):
        from iFactory.application.commands.sync import NoOpIdMapper

        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()

    async def handle(
        self,
        request: SyncLatestStatusCommand,
    ) -> Result[SyncLatestResponse, Error]:
        """Execute the sync operation."""

        if not request.device_ids:
            return Result.success(
                SyncLatestResponse(
                    devices={},
                    count=0,
                    timestamp=datetime.now(),
                )
            )

        try:
            # Convert display IDs to remote IDs
            remote_ids = self._id_mapper.to_remote_ids(list(request.device_ids))

            # Fetch from remote
            remote_records = await self._remote_source.fetch_latest_status(remote_ids)

            if not remote_records:
                return Result.success(
                    SyncLatestResponse(
                        devices={},
                        count=0,
                        timestamp=datetime.now(),
                    )
                )

            # Process and store
            synced_devices = await self._process_records(remote_records)

            return Result.success(
                SyncLatestResponse(
                    devices=synced_devices,
                    count=len(synced_devices),
                    timestamp=datetime.now(),
                )
            )

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return Result.failure(
                Errors.external_service(
                    service="remote_source",
                    message=str(e),
                )
            )

    async def _process_records(
        self,
        records: List[Dict],
    ) -> Dict[str, SyncedDevice]:
        """Process remote records and update storage."""
        from iFactory.domain.entities.device import Device
        from iFactory.domain.enums.machine_status import MachineStatus
        from iFactory.domain.value_objects.equipment_code import EquipmentCode

        synced = {}

        async with self._uow_factory() as uow:
            # Pre-load existing devices
            existing = {}
            if uow.devices:
                try:
                    all_devices = await uow.devices.get_all()
                    existing = {d.equipment_code.value.upper(): d for d in all_devices}
                except Exception as e:
                    logger.warning(f"Failed to load existing devices: {e}")

            devices_to_save = []

            for record in records:
                remote_code = str(record.get("equip_code", "")).strip()
                if not remote_code:
                    continue

                # Map remote ID to display ID
                display_code = self._id_mapper.to_display_id(remote_code)

                # Parse status
                raw_status = record.get("raw_status") or record.get("equip_status") or "0"
                try:
                    status = MachineStatus(int(raw_status))
                except (ValueError, TypeError):
                    status = MachineStatus.UNKNOWN

                timestamp = record.get("last_update") or datetime.now()
                equip_name = record.get("equip_name")
                reason_code = record.get("reason_code")

                # Get or create device
                code_upper = display_code.upper()
                device = existing.get(code_upper)

                if device:
                    if device.sync_status(status, timestamp):
                        device.update_remote_info(equip_name, reason_code)
                        devices_to_save.append(device)
                else:
                    device = Device(
                        equipment_code=EquipmentCode(display_code),
                        current_status=status,
                        last_updated_at=timestamp,
                        equip_name=equip_name,
                        reason_code=reason_code,
                    )
                    existing[code_upper] = device
                    devices_to_save.append(device)

                # Build response
                synced[display_code] = SyncedDevice(
                    equip_code=display_code,
                    status_code=str(status.value),
                    status_name=status.name,
                    last_update=device.last_updated_at,
                    equip_name=device.equip_name,
                    is_active=device.is_active,
                )

            # Save
            if uow.devices and devices_to_save:
                if hasattr(uow.devices, "bulk_save"):
                    await uow.devices.bulk_save(devices_to_save)
                else:
                    for device in devices_to_save:
                        await uow.devices.save(device)

            await uow.commit()

        return synced


# ============================================================================
# Sync History Command
# ============================================================================


@dataclass(frozen=True)
class SyncHistoryCommand(Request[Result[SyncHistoryResponse, Error]]):
    """Command to sync device history for a time range."""

    device_ids: tuple[str, ...]
    start_time: datetime
    end_time: datetime

    @classmethod
    def create(
        cls,
        device_ids: List[str],
        start_time: datetime,
        end_time: datetime,
    ) -> "SyncHistoryCommand":
        return cls(
            device_ids=tuple(device_ids),
            start_time=start_time,
            end_time=end_time,
        )


# Note: Handler similar to SyncHistoryHandler in sync.py
# Omitted for brevity - follows same pattern


__all__ = [
    # DTOs
    "SyncedDevice",
    "SyncLatestResponse",
    "SyncHistoryResponse",
    # Commands
    "SyncLatestStatusCommand",
    "SyncHistoryCommand",
    # Handlers
    "SyncLatestStatusHandler",
]
