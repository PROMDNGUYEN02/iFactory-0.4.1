# File: application/services/sync_orchestrator.py
"""
Sync Orchestrator Service - With ID Mapping Support.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.commands.sync import (
    IDeviceIdMapper,
    NoOpIdMapper,
    SyncLatestStatusHandler,
    SyncLatestStatusRequest,
    SyncLatestStatusResult,
    SyncHistoryHandler,
    SyncHistoryRequest,
    SyncHistoryResult,
    SyncIncrementalHistoryHandler,
    SyncIncrementalRequest,
)

logger = logging.getLogger(__name__)


class SyncEventListener(Protocol):
    """Protocol for sync event callbacks."""

    def __call__(self, result: SyncLatestStatusResult) -> None: ...


class SyncSession:
    """Tracks sync state for a session."""

    def __init__(self):
        self._initial_history_loaded: Set[str] = set()
        self._last_sync_time: Optional[datetime] = None

    def mark_history_loaded(self, device_ids: List[str]) -> None:
        self._initial_history_loaded.update(device_ids)

    def filter_unloaded(self, device_ids: List[str]) -> List[str]:
        return [d for d in device_ids if d not in self._initial_history_loaded]

    def is_history_loaded(self, device_id: str) -> bool:
        return device_id in self._initial_history_loaded

    def record_sync(self) -> None:
        self._last_sync_time = datetime.now()

    @property
    def last_sync_time(self) -> Optional[datetime]:
        return self._last_sync_time

    @property
    def loaded_device_count(self) -> int:
        return len(self._initial_history_loaded)

    def reset(self) -> None:
        self._initial_history_loaded.clear()
        self._last_sync_time = None


class SyncOrchestrator:
    """
    Orchestrates all sync operations with ID mapping support.

    The id_mapper converts between:
    - display_ids: Used in UI (e.g., "ALS01")
    - remote_ids: Used in database queries (e.g., "ASL01")
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
        on_sync_complete: Optional[SyncEventListener] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._on_sync_complete = on_sync_complete

        # Command handlers with ID mapper
        self._latest_handler = SyncLatestStatusHandler(remote_source, uow_factory, self._id_mapper)
        self._history_handler = SyncHistoryHandler(remote_source, uow_factory, self._id_mapper)
        self._incremental_handler = SyncIncrementalHistoryHandler(remote_source, uow_factory, self._id_mapper)

        self._session = SyncSession()
        self._stats = {
            "total_latest_syncs": 0,
            "total_history_syncs": 0,
            "total_incremental_syncs": 0,
        }

    async def sync_latest_status(self, device_ids: List[str]) -> SyncLatestStatusResult:
        """
        Sync latest status for the specified devices.

        Args:
            device_ids: Explicit list of DISPLAY equipment codes to sync.
        """
        if not device_ids:
            logger.debug("[SyncOrchestrator] No device IDs provided for latest sync")
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        request = SyncLatestStatusRequest(device_ids=device_ids)
        result = await self._latest_handler.execute(request)

        self._session.record_sync()
        self._stats["total_latest_syncs"] += 1

        if self._on_sync_complete and result.success:
            self._on_sync_complete(result)

        return result

    async def sync_initial_history(
        self,
        device_ids: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> SyncHistoryResult:
        """
        Sync initial history for devices that haven't been loaded yet.

        Args:
            device_ids: DISPLAY IDs of devices to potentially sync.
        """
        unloaded_ids = self._session.filter_unloaded(device_ids)

        if not unloaded_ids:
            logger.debug("[SyncOrchestrator] All devices already have initial history")
            return SyncHistoryResult()

        now = datetime.now()
        start = start_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = end_time or now

        request = SyncHistoryRequest(
            device_ids=unloaded_ids,
            start_time=start,
            end_time=end,
        )

        result = await self._history_handler.execute(request)

        if result.success:
            self._session.mark_history_loaded(unloaded_ids)
            self._stats["total_history_syncs"] += 1

        logger.info(f"[SyncOrchestrator] Initial history: {result.records_synced} records " f"for {result.devices_processed} devices")

        return result

    async def sync_incremental_history(self, device_ids: List[str], record_limit: int = 2) -> SyncHistoryResult:
        """
        Sync recent history records for incremental updates.

        Args:
            device_ids: DISPLAY IDs of devices to sync.
        """
        if not device_ids:
            return SyncHistoryResult()

        request = SyncIncrementalRequest(
            device_ids=device_ids,
            record_limit=record_limit,
        )

        result = await self._incremental_handler.execute(request)

        if result.records_synced > 0:
            self._stats["total_incremental_syncs"] += 1

        return result

    async def sync_all(
        self,
        device_ids: List[str],
        force_initial_history: bool = False,
    ) -> SyncLatestStatusResult:
        """
        Combined sync: Latest status + History (initial or incremental).

        Args:
            device_ids: DISPLAY IDs of devices to sync.
        """
        if not device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        latest_result = await self.sync_latest_status(device_ids)

        unloaded_ids = self._session.filter_unloaded(device_ids)

        if unloaded_ids or force_initial_history:
            ids_to_load = device_ids if force_initial_history else unloaded_ids
            await self.sync_initial_history(ids_to_load)
        else:
            await self.sync_incremental_history(device_ids)

        return latest_result

    def reset_session(self) -> None:
        """Reset session state."""
        self._session.reset()
        logger.info("[SyncOrchestrator] Session reset")

    def is_device_history_loaded(self, device_id: str) -> bool:
        """Check if a device has had its initial history loaded."""
        return self._session.is_history_loaded(device_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            **self._stats,
            "last_sync": self._session.last_sync_time,
            "devices_with_history": self._session.loaded_device_count,
        }

    def set_page_devices(self, device_codes: List[str]) -> None:
        """DEPRECATED: Pass device_ids directly to sync methods."""
        import warnings

        warnings.warn(
            "set_page_devices() is deprecated. Pass device_ids directly to sync methods.",
            DeprecationWarning,
            stacklevel=2,
        )


def create_sync_orchestrator(
    remote_source: IRemoteDataSource,
    uow_factory: Callable[[], AbstractUnitOfWork],
    id_mapper: Optional[IDeviceIdMapper] = None,
    on_sync_complete: Optional[SyncEventListener] = None,
) -> SyncOrchestrator:
    """Factory function to create a SyncOrchestrator."""
    return SyncOrchestrator(
        remote_source=remote_source,
        uow_factory=uow_factory,
        id_mapper=id_mapper,
        on_sync_complete=on_sync_complete,
    )


__all__ = [
    "SyncOrchestrator",
    "SyncSession",
    "SyncEventListener",
    "create_sync_orchestrator",
]
