# src/iFactory/application/services/sync_orchestrator.py
"""
Sync Orchestrator Service - With Availability Deduplication.

FIXES:
- Dedup concurrent availability requests
- Longer cache TTL (10s instead of 5s)
- Better disposed check
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
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
    SyncedDeviceData,
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


# =============================================================================
# Availability Data
# =============================================================================


@dataclass
class DeviceAvailability:
    """Availability data for a single device."""

    device_id: str
    availability: float  # Percentage 0-100
    run_time_seconds: float
    total_time_seconds: float
    timestamp: datetime

    @property
    def age_seconds(self) -> float:
        """Get age of this data in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    def is_fresh(self, max_age: float = 10.0) -> bool:
        """Check if data is fresh (default 10 seconds)."""
        return self.age_seconds < max_age


class SyncOrchestrator:
    """
    Orchestrates all sync operations with Availability Deduplication.

    FIXES:
    - Dedup: Only one concurrent availability fetch per device
    - Cache TTL increased to 10s
    - Check disposed before callbacks
    """

    AVAILABILITY_CACHE_TTL = 10.0  # seconds

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
        self._is_disposed = False

        # Command handlers with ID mapper
        self._latest_handler = SyncLatestStatusHandler(remote_source, uow_factory, self._id_mapper)
        self._history_handler = SyncHistoryHandler(remote_source, uow_factory, self._id_mapper)
        self._incremental_handler = SyncIncrementalHistoryHandler(remote_source, uow_factory, self._id_mapper)

        self._session = SyncSession()

        # Availability cache (device_id -> DeviceAvailability)
        self._availability_cache: Dict[str, DeviceAvailability] = {}

        # NEW: Track pending availability fetches to dedup
        self._pending_availability: Dict[str, asyncio.Task] = {}
        self._availability_lock = asyncio.Lock()

        self._stats = {
            "total_latest_syncs": 0,
            "total_history_syncs": 0,
            "total_incremental_syncs": 0,
            "total_availability_fetches": 0,
            "availability_cache_hits": 0,
            "availability_dedup_hits": 0,
        }

    def dispose(self) -> None:
        """Mark orchestrator as disposed."""
        self._is_disposed = True

        # Cancel pending tasks
        for task in self._pending_availability.values():
            if not task.done():
                task.cancel()
        self._pending_availability.clear()

    async def sync_latest_status(
        self,
        device_ids: List[str],
    ) -> SyncLatestStatusResult:
        """Sync latest status for the specified devices."""
        if self._is_disposed:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        if not device_ids:
            logger.debug("[SyncOrchestrator] No device IDs provided for latest sync")
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        request = SyncLatestStatusRequest(device_ids=device_ids)
        result = await self._latest_handler.execute(request)

        self._session.record_sync()
        self._stats["total_latest_syncs"] += 1

        if self._on_sync_complete and result.success and not self._is_disposed:
            self._on_sync_complete(result)

        return result

    async def fetch_device_availability(
        self,
        device_id: str,
        force_refresh: bool = False,
    ) -> Optional[DeviceAvailability]:
        """
        Fetch availability for a single device with deduplication.

        Features:
        - Uses cache if available and fresh (< 10 seconds old)
        - Deduplicates concurrent requests for same device
        """
        if self._is_disposed:
            return None

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self._availability_cache.get(device_id)
            if cached and cached.is_fresh(self.AVAILABILITY_CACHE_TTL):
                self._stats["availability_cache_hits"] += 1
                logger.debug(f"[SyncOrchestrator] Availability cache hit for {device_id}")
                return cached

        # Check for pending request (dedup)
        async with self._availability_lock:
            pending_task = self._pending_availability.get(device_id)
            if pending_task and not pending_task.done():
                self._stats["availability_dedup_hits"] += 1
                logger.debug(f"[SyncOrchestrator] Dedup: waiting for pending {device_id}")
                try:
                    return await pending_task
                except Exception:
                    return None

            # Create new task
            task = asyncio.create_task(self._do_fetch_availability(device_id))
            self._pending_availability[device_id] = task

        try:
            result = await task
            return result
        finally:
            # Cleanup pending task
            async with self._availability_lock:
                self._pending_availability.pop(device_id, None)

    async def _do_fetch_availability(
        self,
        device_id: str,
    ) -> Optional[DeviceAvailability]:
        """Actually fetch availability (internal)."""
        if self._is_disposed:
            return None

        logger.info(f"[SyncOrchestrator] Fetching availability for {device_id}")

        try:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            total_seconds = (now - today_start).total_seconds()

            if total_seconds <= 0:
                return None

            # Convert display ID to remote ID
            remote_id = self._id_mapper.to_remote_id(device_id)

            # Fetch from remote
            run_time = 0.0
            if hasattr(self._remote_source, "fetch_single_device_run_time"):
                run_time = await self._remote_source.fetch_single_device_run_time(remote_id)
            elif hasattr(self._remote_source, "fetch_today_run_times"):
                run_times = await self._remote_source.fetch_today_run_times([remote_id])
                run_time = run_times.get(remote_id.upper(), 0.0)
            else:
                logger.warning("[SyncOrchestrator] No run time fetch method available")
                return None

            if self._is_disposed:
                return None

            # Calculate availability
            availability = (run_time / total_seconds) * 100 if total_seconds > 0 else 0.0
            availability = min(availability, 100.0)

            # Create and cache result
            result = DeviceAvailability(
                device_id=device_id,
                availability=availability,
                run_time_seconds=run_time,
                total_time_seconds=total_seconds,
                timestamp=now,
            )

            self._availability_cache[device_id] = result
            self._stats["total_availability_fetches"] += 1

            logger.info(
                f"[SyncOrchestrator] Availability for {device_id}: " f"{availability:.1f}% (Run: {run_time:.0f}s / Total: {total_seconds:.0f}s)"
            )

            return result

        except Exception as e:
            if not self._is_disposed:
                logger.error(f"[SyncOrchestrator] Failed to fetch availability for {device_id}: {e}")
            return None

    def get_cached_availability(self, device_id: str) -> Optional[DeviceAvailability]:
        """Get cached availability without fetching."""
        return self._availability_cache.get(device_id)

    def clear_availability_cache(self, device_id: Optional[str] = None) -> None:
        """Clear availability cache for a device or all devices."""
        if device_id:
            self._availability_cache.pop(device_id, None)
        else:
            self._availability_cache.clear()

    async def sync_initial_history(
        self,
        device_ids: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> SyncHistoryResult:
        """Sync initial history for devices that haven't been loaded yet."""
        if self._is_disposed:
            return SyncHistoryResult()

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

    async def sync_incremental_history(
        self,
        device_ids: List[str],
        record_limit: int = 2,
    ) -> SyncHistoryResult:
        """Sync recent history records for incremental updates."""
        if self._is_disposed:
            return SyncHistoryResult()

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
        """Combined sync: Latest status + History (initial or incremental)."""
        if self._is_disposed:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

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
        """Reset session state and availability cache."""
        self._session.reset()
        self._availability_cache.clear()
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
            "availability_cache_size": len(self._availability_cache),
            "pending_availability_fetches": len(self._pending_availability),
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
    "DeviceAvailability",
    "create_sync_orchestrator",
]
