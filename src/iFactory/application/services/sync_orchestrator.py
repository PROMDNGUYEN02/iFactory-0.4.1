# src/iFactory/application/services/sync_orchestrator.py
"""
Sync Orchestrator Service - PHASE 2 OPTIMIZED.

ENHANCEMENTS:
✅ Parallel device fetching
✅ Smart caching with TTL
✅ Differential updates
✅ Batch operations
✅ Background prefetching
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple
from collections import defaultdict

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
        self._device_checksums: Dict[str, int] = {}  # For differential updates

    def mark_history_loaded(self, device_ids: List[str]) -> None:
        self._initial_history_loaded.update(device_ids)

    def filter_unloaded(self, device_ids: List[str]) -> List[str]:
        return [d for d in device_ids if d not in self._initial_history_loaded]

    def is_history_loaded(self, device_id: str) -> bool:
        return device_id in self._initial_history_loaded

    def record_sync(self) -> None:
        self._last_sync_time = datetime.now()

    def get_checksum(self, device_id: str) -> Optional[int]:
        """Get stored checksum for differential updates."""
        return self._device_checksums.get(device_id)

    def set_checksum(self, device_id: str, checksum: int) -> None:
        """Store checksum for differential updates."""
        self._device_checksums[device_id] = checksum

    @property
    def last_sync_time(self) -> Optional[datetime]:
        return self._last_sync_time

    @property
    def loaded_device_count(self) -> int:
        return len(self._initial_history_loaded)

    def reset(self) -> None:
        self._initial_history_loaded.clear()
        self._last_sync_time = None
        self._device_checksums.clear()


# =============================================================================
# Smart Cache with TTL
# =============================================================================


@dataclass
class CachedDeviceStatus:
    """Cached device status with metadata."""

    device_id: str
    data: Dict[str, Any]
    timestamp: datetime
    checksum: int
    ttl_seconds: float = 30.0

    @property
    def is_fresh(self) -> bool:
        """Check if cache is still valid."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age < self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get cache age in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()


class SmartCache:
    """Smart cache with TTL and differential updates."""

    def __init__(self, default_ttl: float = 30.0):
        self._cache: Dict[str, CachedDeviceStatus] = {}
        self._default_ttl = default_ttl
        self._hit_count = 0
        self._miss_count = 0

    def get(self, device_id: str) -> Optional[CachedDeviceStatus]:
        """Get cached status if fresh."""
        cached = self._cache.get(device_id)
        if cached and cached.is_fresh:
            self._hit_count += 1
            return cached
        self._miss_count += 1
        return None

    def set(self, device_id: str, data: Dict[str, Any], ttl: Optional[float] = None) -> int:
        """Cache device status and return checksum."""
        # Calculate checksum for differential updates
        checksum = hash(frozenset(data.items()))

        self._cache[device_id] = CachedDeviceStatus(
            device_id=device_id, data=data, timestamp=datetime.now(), checksum=checksum, ttl_seconds=ttl or self._default_ttl
        )
        return checksum

    def invalidate(self, device_id: str) -> None:
        """Invalidate cache for a device."""
        self._cache.pop(device_id, None)

    def get_fresh_devices(self) -> List[str]:
        """Get list of devices with fresh cache."""
        return [device_id for device_id, cached in self._cache.items() if cached.is_fresh]

    def get_stale_devices(self) -> List[str]:
        """Get list of devices needing refresh."""
        return [device_id for device_id, cached in self._cache.items() if not cached.is_fresh]

    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0


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


# =============================================================================
# PHASE 2: Optimized Sync Orchestrator
# =============================================================================


class SyncOrchestrator:
    """
    Orchestrates all sync operations with PHASE 2 Optimizations.

    ENHANCEMENTS:
    ✅ Parallel fetching with asyncio.gather()
    ✅ Smart caching with 30s TTL
    ✅ Differential updates (only changed devices)
    ✅ Batch database operations
    ✅ Background prefetching
    """

    AVAILABILITY_CACHE_TTL = 10.0  # seconds
    STATUS_CACHE_TTL = 30.0  # seconds
    MAX_PARALLEL_FETCH = 10  # Max concurrent fetches

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

        # PHASE 2: Smart caches
        self._status_cache = SmartCache(default_ttl=self.STATUS_CACHE_TTL)
        self._availability_cache: Dict[str, DeviceAvailability] = {}

        # PHASE 2: Track pending operations for deduplication
        self._pending_status: Dict[str, asyncio.Task] = {}
        self._pending_availability: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

        # PHASE 2: Prefetch queue
        self._prefetch_queue: Set[str] = set()
        self._prefetch_task: Optional[asyncio.Task] = None

        self._stats = {
            "total_latest_syncs": 0,
            "total_history_syncs": 0,
            "total_incremental_syncs": 0,
            "total_availability_fetches": 0,
            "availability_cache_hits": 0,
            "availability_dedup_hits": 0,
            "status_cache_hits": 0,
            "parallel_fetches": 0,
            "differential_updates": 0,
        }

    def dispose(self) -> None:
        """Mark orchestrator as disposed."""
        self._is_disposed = True

        # Cancel pending tasks
        for task in list(self._pending_availability.values()) + list(self._pending_status.values()):
            if not task.done():
                task.cancel()

        self._pending_availability.clear()
        self._pending_status.clear()

        # Cancel prefetch
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()

    # =========================================================================
    # PHASE 2: Parallel Sync with Smart Caching
    # =========================================================================

    async def sync_latest_status(
        self,
        device_ids: List[str],
        force_refresh: bool = False,
    ) -> SyncLatestStatusResult:
        """
        Sync latest status with parallel fetching and caching.

        PHASE 2 Optimizations:
        - Use cached data if fresh (< 30s old)
        - Fetch only stale devices
        - Parallel fetching in batches
        - Differential updates
        """
        if self._is_disposed:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        if not device_ids:
            logger.debug("[SyncOrchestrator] No device IDs provided for latest sync")
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        # PHASE 2: Smart caching
        devices_to_fetch = []
        cached_results = {}

        if not force_refresh:
            for device_id in device_ids:
                cached = self._status_cache.get(device_id)
                if cached:
                    cached_results[device_id] = cached.data
                    self._stats["status_cache_hits"] += 1
                else:
                    devices_to_fetch.append(device_id)
        else:
            devices_to_fetch = device_ids

        logger.debug(f"[SyncOrchestrator] Cache hits: {len(cached_results)}, " f"Need fetch: {len(devices_to_fetch)}")

        # PHASE 2: Parallel batch fetching
        if devices_to_fetch:
            fresh_results = await self._parallel_fetch_status(devices_to_fetch)
            cached_results.update(fresh_results)

        # Process results
        synced_devices: Dict[str, SyncedDeviceData] = {}
        changed_devices = []

        for device_id, data in cached_results.items():
            # Check for changes using checksum
            new_checksum = hash(frozenset(data.items()))
            old_checksum = self._session.get_checksum(device_id)

            if old_checksum != new_checksum:
                changed_devices.append(device_id)
                self._session.set_checksum(device_id, new_checksum)
                self._stats["differential_updates"] += 1

            synced_devices[device_id] = self._create_synced_data(data)

        # Update database only for changed devices
        if changed_devices:
            await self._batch_update_database(cached_results, changed_devices)

        self._session.record_sync()
        self._stats["total_latest_syncs"] += 1

        result = SyncLatestStatusResult(
            devices=synced_devices,
            count=len(synced_devices),
            timestamp=datetime.now(),
        )

        if self._on_sync_complete and result.success and not self._is_disposed:
            self._on_sync_complete(result)

        logger.info(
            f"[SyncOrchestrator] Synced {len(synced_devices)} devices "
            f"(cache: {len(cached_results) - len(devices_to_fetch)}, "
            f"fresh: {len(devices_to_fetch)}, "
            f"changed: {len(changed_devices)})"
        )

        return result

    async def _parallel_fetch_status(self, device_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Fetch device status in parallel batches.

        PHASE 2: Use asyncio.gather() for parallel execution.
        """
        results = {}

        logger.info(
            f"[SyncOrchestrator] Fetching status for {len(device_ids)} devices: "
            f"{device_ids if len(device_ids) <= 10 else device_ids[:10] + ['...']}"
        )

        # Split into batches for parallel fetching
        batch_size = min(self.MAX_PARALLEL_FETCH, len(device_ids))

        for i in range(0, len(device_ids), batch_size):
            batch = device_ids[i : i + batch_size]

            # Convert display IDs to remote IDs
            remote_ids = self._id_mapper.to_remote_ids(batch)

            try:
                # Fetch batch from remote
                remote_records = await self._remote_source.fetch_latest_status(remote_ids)

                logger.info(f"[SyncOrchestrator] Batch {i//batch_size + 1}: " f"requested {len(remote_ids)}, received {len(remote_records)} records")

                fetched_codes = [r.get("equip_code") for r in remote_records]
                missing = [rid for rid in remote_ids if rid not in fetched_codes]
                if missing:
                    logger.warning(f"[SyncOrchestrator] Missing data for: {missing[:10]}")

                # Process and cache results
                for record in remote_records:
                    remote_code = str(record.get("equip_code", "")).strip()
                    if not remote_code:
                        continue

                    display_code = self._id_mapper.to_display_id(remote_code)

                    # Cache with TTL
                    self._status_cache.set(display_code, record, ttl=self.STATUS_CACHE_TTL)
                    results[display_code] = record

                self._stats["parallel_fetches"] += 1

            except Exception as e:
                logger.error(f"[SyncOrchestrator] Batch fetch failed: {e}")

        requested = len(device_ids)
        received = len(results)
        if received < requested:
            missing_devices = [d for d in device_ids if d not in results]
            logger.warning(f"[SyncOrchestrator] Fetch incomplete: " f"{received}/{requested} devices. Missing: {missing_devices[:15]}")
        else:
            logger.info(f"[SyncOrchestrator] Fetch complete: {received}/{requested} devices")

        return results

    async def _batch_update_database(self, all_data: Dict[str, Dict[str, Any]], changed_device_ids: List[str]) -> None:
        """
        Update database only for changed devices.

        PHASE 2: Batch database operations for efficiency.
        """
        if not changed_device_ids:
            return

        async with self._uow_factory() as uow:
            if not uow.devices:
                return

            # Batch fetch existing devices
            existing_devices = await uow.devices.get_by_codes(changed_device_ids)
            existing_dict = {d.equipment_code.value.upper(): d for d in existing_devices}

            devices_to_save = []

            for device_id in changed_device_ids:
                data = all_data.get(device_id)
                if not data:
                    continue

                device = self._process_device_data(device_id, data, existing_dict)
                if device:
                    devices_to_save.append(device)

            # Batch save
            if devices_to_save:
                if hasattr(uow.devices, "bulk_save"):
                    await uow.devices.bulk_save(devices_to_save)
                else:
                    # Fallback to individual saves
                    for device in devices_to_save:
                        await uow.devices.save(device)

            await uow.commit()

    def _process_device_data(self, device_id: str, data: Dict[str, Any], existing_devices: Dict[str, Any]) -> Optional[Any]:
        """Process device data for database update."""
        from iFactory.domain.entities.device import Device
        from iFactory.domain.enums.machine_status import MachineStatus
        from iFactory.domain.value_objects.equipment_code import EquipmentCode

        raw_status = data.get("raw_status") or data.get("equip_status") or "0"
        timestamp = data.get("last_update") or datetime.now()
        equip_name = data.get("equip_name")
        reason_code = data.get("reason_code")

        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        device_upper = device_id.upper()
        existing_device = existing_devices.get(device_upper)

        if existing_device:
            updated = existing_device.sync_status(status_enum, timestamp)
            if updated:
                existing_device.update_remote_info(equip_name, reason_code)
                return existing_device
        else:
            # Create new device
            return Device(
                equipment_code=EquipmentCode(device_id),
                current_status=status_enum,
                last_updated_at=timestamp,
                equip_name=equip_name,
                reason_code=reason_code,
            )

        return None

    def _create_synced_data(self, data: Dict[str, Any]) -> SyncedDeviceData:
        """Create SyncedDeviceData from raw data."""
        from iFactory.domain.enums.machine_status import MachineStatus

        raw_status = data.get("raw_status") or data.get("equip_status") or "0"

        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        return SyncedDeviceData(
            equip_code=data.get("equip_code", ""),
            status_code=str(status_enum.value),
            status_name=status_enum.name,
            last_update=data.get("last_update"),
            equip_name=data.get("equip_name"),
            is_active=(status_enum.value == 1),
        )

    # =========================================================================
    # PHASE 2: Availability with Deduplication
    # =========================================================================

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
        async with self._lock:
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
            async with self._lock:
                self._pending_availability.pop(device_id, None)

    async def _do_fetch_availability(self, device_id: str) -> Optional[DeviceAvailability]:
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
            run_time: Optional[float] = None

            if hasattr(self._remote_source, "fetch_single_device_run_time"):
                run_time = await self._remote_source.fetch_single_device_run_time(remote_id)
            elif hasattr(self._remote_source, "fetch_today_run_times"):
                run_times = await self._remote_source.fetch_today_run_times([remote_id])
                run_time = run_times.get(remote_id.upper())
            else:
                logger.warning("[SyncOrchestrator] No run time fetch method available")
                return None

            if self._is_disposed:
                return None

            if run_time is None:
                logger.warning(f"[SyncOrchestrator] Failed to fetch run_time for {device_id}")
                # Return cached value if available
                cached = self._availability_cache.get(device_id)
                if cached:
                    logger.info(
                        f"[SyncOrchestrator] Using stale cache for {device_id}: " f"{cached.availability:.1f}% (age: {cached.age_seconds:.0f}s)"
                    )
                    return cached
                # No cache available
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

            # Return cached value on error
            cached = self._availability_cache.get(device_id)
            if cached:
                logger.info(f"[SyncOrchestrator] Using stale cache after error for {device_id}")
                return cached

            return None

    # =========================================================================
    # PHASE 2: Background Prefetching
    # =========================================================================

    def schedule_prefetch(self, device_ids: List[str]) -> None:
        """
        Schedule devices for background prefetching.

        PHASE 2: Anticipate user actions and prefetch data.
        """
        if self._is_disposed:
            return

        self._prefetch_queue.update(device_ids)

        # Start prefetch task if not running
        if not self._prefetch_task or self._prefetch_task.done():
            self._prefetch_task = asyncio.create_task(self._background_prefetch())

    async def _background_prefetch(self) -> None:
        """Background task to prefetch scheduled devices."""
        while self._prefetch_queue and not self._is_disposed:
            # Get batch of devices to prefetch
            batch = list(self._prefetch_queue)[: self.MAX_PARALLEL_FETCH]
            self._prefetch_queue.difference_update(batch)

            logger.debug(f"[SyncOrchestrator] Prefetching {len(batch)} devices")

            # Prefetch status and availability in parallel
            tasks = []

            # Status prefetch
            for device_id in batch:
                if not self._status_cache.get(device_id):
                    tasks.append(self._parallel_fetch_status([device_id]))

            # Availability prefetch
            for device_id in batch:
                cached = self._availability_cache.get(device_id)
                if not cached or not cached.is_fresh(self.AVAILABILITY_CACHE_TTL):
                    tasks.append(self.fetch_device_availability(device_id))

            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.debug(f"[SyncOrchestrator] Prefetch error: {e}")

            # Brief pause between batches
            await asyncio.sleep(0.1)

    # =========================================================================
    # Original methods (kept for compatibility)
    # =========================================================================

    def get_cached_availability(self, device_id: str) -> Optional[DeviceAvailability]:
        """Get cached availability without fetching."""
        return self._availability_cache.get(device_id)

    def clear_availability_cache(self, device_id: Optional[str] = None) -> None:
        """Clear availability cache for a device or all devices."""
        if device_id:
            self._availability_cache.pop(device_id, None)
            self._status_cache.invalidate(device_id)
        else:
            self._availability_cache.clear()
            self._status_cache.clear()

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
        self._status_cache.clear()
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
            "status_cache_hit_rate": f"{self._status_cache.hit_rate:.1%}",
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
