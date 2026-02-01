# File: application/services/sync_orchestrator.py
"""
Sync Orchestrator Service.

Coordinates sync operations as an Application Layer facade.
This service is UI-AGNOSTIC - it operates on explicit device IDs
provided by callers, not on implicit UI state.

The Presentation Layer (e.g., Controllers) is responsible for:
- Determining which devices are currently visible/relevant
- Calling the orchestrator with explicit device ID lists
- Handling the sync results for UI updates
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, Set

from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.commands.sync import (
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


# =============================================================================
# Callback Protocol for Sync Events
# =============================================================================


class SyncEventListener(Protocol):
    """Protocol for sync event callbacks."""

    def __call__(self, result: SyncLatestStatusResult) -> None:
        """Handle sync completion event."""
        ...


# =============================================================================
# Sync Session State
# =============================================================================


class SyncSession:
    """
    Tracks sync state for a session.

    This is Application Layer state, not UI state.
    It tracks which devices have had their initial history loaded
    to avoid redundant fetches.
    """

    def __init__(self):
        self._initial_history_loaded: Set[str] = set()
        self._last_sync_time: Optional[datetime] = None

    def mark_history_loaded(self, device_ids: List[str]) -> None:
        """Mark devices as having initial history loaded."""
        self._initial_history_loaded.update(device_ids)

    def filter_unloaded(self, device_ids: List[str]) -> List[str]:
        """Return only devices that haven't had initial history loaded."""
        return [d for d in device_ids if d not in self._initial_history_loaded]

    def is_history_loaded(self, device_id: str) -> bool:
        """Check if a device has had initial history loaded."""
        return device_id in self._initial_history_loaded

    def record_sync(self) -> None:
        """Record that a sync occurred."""
        self._last_sync_time = datetime.now()

    @property
    def last_sync_time(self) -> Optional[datetime]:
        return self._last_sync_time

    @property
    def loaded_device_count(self) -> int:
        return len(self._initial_history_loaded)

    def reset(self) -> None:
        """Reset session state (e.g., on reconnect)."""
        self._initial_history_loaded.clear()
        self._last_sync_time = None


# =============================================================================
# Sync Orchestrator
# =============================================================================


class SyncOrchestrator:
    """
    Orchestrates all sync operations.

    This is a Facade/Coordinator that:
    1. Delegates to appropriate command handlers
    2. Manages session state (initial history tracking)
    3. Provides a simple API for the Presentation Layer

    UI Decoupling:
    - All methods accept explicit device_ids parameters
    - No internal tracking of "current page" or UI concepts
    - Callers are responsible for determining which devices to sync
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        on_sync_complete: Optional[SyncEventListener] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._on_sync_complete = on_sync_complete

        # Command handlers
        self._latest_handler = SyncLatestStatusHandler(remote_source, uow_factory)
        self._history_handler = SyncHistoryHandler(remote_source, uow_factory)
        self._incremental_handler = SyncIncrementalHistoryHandler(remote_source, uow_factory)

        # Session state
        self._session = SyncSession()

        # Statistics
        self._stats = {
            "total_latest_syncs": 0,
            "total_history_syncs": 0,
            "total_incremental_syncs": 0,
        }

    # -------------------------------------------------------------------------
    # Primary Sync Methods (Explicit Device IDs)
    # -------------------------------------------------------------------------

    async def sync_latest_status(self, device_ids: List[str]) -> SyncLatestStatusResult:
        """
        Sync latest status for the specified devices.

        Args:
            device_ids: Explicit list of equipment codes to sync.
                       Empty list results in no-op.

        Returns:
            SyncLatestStatusResult with synced device data.
        """
        if not device_ids:
            logger.debug("[SyncOrchestrator] No device IDs provided for latest sync")
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        request = SyncLatestStatusRequest(device_ids=device_ids)
        result = await self._latest_handler.execute(request)

        self._session.record_sync()
        self._stats["total_latest_syncs"] += 1

        # Notify listeners
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
            device_ids: Devices to potentially sync.
            start_time: Start of range (default: 00:00 today).
            end_time: End of range (default: now).

        Returns:
            SyncHistoryResult with count of synced records.

        Note:
            Automatically filters out devices that have already had
            initial history loaded this session.
        """
        # Filter to only unloaded devices
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
            device_ids: Devices to sync.
            record_limit: Number of recent records per device.

        Returns:
            SyncHistoryResult with count of updated records.
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
            device_ids: Devices to sync.
            force_initial_history: If True, reload history even if already loaded.

        Returns:
            SyncLatestStatusResult from the latest status sync.
        """
        if not device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        # Sync latest status
        latest_result = await self.sync_latest_status(device_ids)

        # Determine history sync strategy
        unloaded_ids = self._session.filter_unloaded(device_ids)

        if unloaded_ids or force_initial_history:
            # Initial load for new devices
            ids_to_load = device_ids if force_initial_history else unloaded_ids
            await self.sync_initial_history(ids_to_load)
        else:
            # Incremental for already loaded devices
            await self.sync_incremental_history(device_ids)

        return latest_result

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------

    def reset_session(self) -> None:
        """
        Reset session state.

        Call this when:
        - User explicitly requests refresh
        - Connection is re-established after failure
        - Application needs to reload all data
        """
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

    # -------------------------------------------------------------------------
    # Deprecated Methods (Backward Compatibility)
    # -------------------------------------------------------------------------

    def set_page_devices(self, device_codes: List[str]) -> None:
        """
        DEPRECATED: This method exists for backward compatibility only.

        The Application Layer should not track UI concepts like "pages".
        Instead, callers should pass device_ids directly to sync methods.

        This method now does nothing but log a deprecation warning.
        """
        import warnings

        warnings.warn(
            "set_page_devices() is deprecated. " "Pass device_ids directly to sync methods instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            "[SyncOrchestrator] DEPRECATED: set_page_devices() called. "
            "This method no longer has any effect. "
            "Pass device_ids directly to sync methods."
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_sync_orchestrator(
    remote_source: IRemoteDataSource,
    uow_factory: Callable[[], AbstractUnitOfWork],
    on_sync_complete: Optional[SyncEventListener] = None,
) -> SyncOrchestrator:
    """
    Factory function to create a SyncOrchestrator.

    This is the recommended way to instantiate the orchestrator,
    ensuring all dependencies are properly injected.
    """
    return SyncOrchestrator(
        remote_source=remote_source,
        uow_factory=uow_factory,
        on_sync_complete=on_sync_complete,
    )


__all__ = [
    "SyncOrchestrator",
    "SyncSession",
    "SyncEventListener",
    "create_sync_orchestrator",
]
