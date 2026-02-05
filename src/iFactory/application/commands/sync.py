# src/iFactory/application/commands/sync.py
"""
Optimized Sync Commands with Batch Operations.

OPTIMIZATION CONCEPTS IMPLEMENTED:
1. Batch Repository Operations - Bulk database operations
2. Memory-Optimized Models - Slots, frozen dataclasses
3. Request Batching - Automatic request aggregation
4. Parallel Execution - Concurrent chunk processing
5. Progressive Results - Yield results as available

Version: 2.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Constants
# =============================================================================

# Batch configuration
DEFAULT_BATCH_SIZE = 20
MAX_BATCH_SIZE = 50
BATCH_DEBOUNCE_MS = 100
MAX_CONCURRENT_BATCHES = 4
CHUNK_SIZE = 5

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY_MS = 1000

# Cache configuration
CACHE_TTL_SECONDS = 30


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

    __slots__ = ()

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        return display_ids

    def to_display_id(self, remote_id: str) -> str:
        return remote_id

    def to_remote_id(self, display_id: str) -> str:
        return display_id


# =============================================================================
# Memory-Optimized Data Models
# =============================================================================


@dataclass(frozen=True, slots=True)
class SyncLatestStatusRequest:
    """
    Immutable request for latest status sync.

    Uses frozen=True for immutability and hashability.
    Uses slots=True for memory efficiency.
    """

    device_ids: Tuple[str, ...]  # Tuple for immutability
    priority: int = 0  # 0 = normal, higher = more urgent
    skip_cache: bool = False

    @classmethod
    def from_list(
        cls,
        device_ids: List[str],
        priority: int = 0,
        skip_cache: bool = False,
    ) -> "SyncLatestStatusRequest":
        """Create from list (converts to tuple)."""
        return cls(
            device_ids=tuple(device_ids),
            priority=priority,
            skip_cache=skip_cache,
        )

    def __hash__(self) -> int:
        return hash(self.device_ids)


@dataclass(frozen=True, slots=True)
class SyncHistoryRequest:
    """Immutable request for history sync."""

    device_ids: Tuple[str, ...]
    start_time: datetime
    end_time: datetime

    @classmethod
    def from_list(
        cls,
        device_ids: List[str],
        start_time: datetime,
        end_time: datetime,
    ) -> "SyncHistoryRequest":
        return cls(
            device_ids=tuple(device_ids),
            start_time=start_time,
            end_time=end_time,
        )


@dataclass(frozen=True, slots=True)
class SyncIncrementalRequest:
    """Immutable request for incremental sync."""

    device_ids: Tuple[str, ...]
    record_limit: int = 2

    @classmethod
    def from_list(
        cls,
        device_ids: List[str],
        record_limit: int = 2,
    ) -> "SyncIncrementalRequest":
        return cls(
            device_ids=tuple(device_ids),
            record_limit=record_limit,
        )


@dataclass(frozen=True, slots=True)
class SyncedDeviceData:
    """
    Memory-optimized device data transfer object.

    Immutable for thread safety and reduced memory churn.
    """

    equip_code: str
    status_code: int  # Use int instead of str for memory
    status_name: str
    last_update: Optional[datetime]
    equip_name: Optional[str]
    is_active: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for serialization)."""
        return {
            "equip_code": self.equip_code,
            "status_code": str(self.status_code),
            "status_name": self.status_name,
            "last_update": self.last_update,
            "equip_name": self.equip_name,
            "is_active": self.is_active,
        }


@dataclass(slots=True)
class SyncLatestStatusResult:
    """Result of a latest status sync operation."""

    devices: Dict[str, SyncedDeviceData] = field(default_factory=dict)
    count: int = 0
    timestamp: Optional[datetime] = None
    error: Optional[str] = None
    from_cache: bool = False
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None

    def merge(self, other: "SyncLatestStatusResult") -> "SyncLatestStatusResult":
        """Merge two results."""
        merged_devices = {**self.devices, **other.devices}
        return SyncLatestStatusResult(
            devices=merged_devices,
            count=len(merged_devices),
            timestamp=other.timestamp or self.timestamp,
            error=other.error or self.error,
            from_cache=self.from_cache and other.from_cache,
            duration_ms=max(self.duration_ms, other.duration_ms),
        )


@dataclass(slots=True)
class SyncHistoryResult:
    """Result of a history sync operation."""

    records_synced: int = 0
    devices_processed: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.error is None


# =============================================================================
# Batch Request Manager
# =============================================================================


class BatchRequestManager:
    """
    Manages automatic batching of sync requests.

    Features:
    - Request aggregation with debouncing
    - Size-based batch splitting
    - Priority ordering
    - Deduplication
    - In-flight tracking
    """

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        debounce_ms: int = BATCH_DEBOUNCE_MS,
        max_concurrent: int = MAX_CONCURRENT_BATCHES,
    ):
        self._batch_size = batch_size
        self._debounce_ms = debounce_ms
        self._max_concurrent = max_concurrent

        # Pending requests by priority
        self._pending: Dict[int, Set[str]] = defaultdict(set)

        # In-flight tracking
        self._in_flight: Set[str] = set()

        # Futures for waiting callers
        self._waiters: List[Tuple[Set[str], asyncio.Future]] = []

        # State
        self._batch_task: Optional[asyncio.Task] = None
        self._debounce_event = asyncio.Event()
        self._lock = asyncio.Lock()

        # Stats
        self._stats = {
            "requests_received": 0,
            "requests_batched": 0,
            "batches_executed": 0,
            "duplicates_skipped": 0,
        }

    async def add_request(
        self,
        device_ids: List[str],
        priority: int = 0,
    ) -> asyncio.Future:
        """
        Add devices to pending batch.

        Args:
            device_ids: Devices to sync
            priority: Higher priority = processed first

        Returns:
            Future that resolves with the batch result
        """
        async with self._lock:
            self._stats["requests_received"] += 1

            # Filter already in-flight
            new_ids = set(device_ids) - self._in_flight

            if not new_ids:
                self._stats["duplicates_skipped"] += 1
                future = asyncio.Future()
                future.set_result(SyncLatestStatusResult(count=0))
                return future

            # Add to pending
            self._pending[priority].update(new_ids)
            self._stats["requests_batched"] += len(new_ids)

            # Create future for this request
            future = asyncio.Future()
            self._waiters.append((new_ids, future))

            # Trigger debounced processing
            self._debounce_event.set()

            # Start batch processor if not running
            if self._batch_task is None or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._process_loop())

            return future

    async def _process_loop(self) -> None:
        """Main processing loop with debouncing."""
        while True:
            # Wait for requests or debounce timeout
            try:
                await asyncio.wait_for(
                    self._debounce_event.wait(),
                    timeout=self._debounce_ms / 1000,
                )
            except asyncio.TimeoutError:
                pass

            self._debounce_event.clear()

            # Check if there's work to do
            async with self._lock:
                if not any(self._pending.values()):
                    break

                # Take batch from highest priority
                batch = await self._take_batch()

            if batch:
                await self._execute_batch(batch)

    async def _take_batch(self) -> List[str]:
        """Take a batch of devices to process."""
        batch: List[str] = []

        # Process priorities in descending order
        for priority in sorted(self._pending.keys(), reverse=True):
            pending_set = self._pending[priority]

            while pending_set and len(batch) < self._batch_size:
                device_id = pending_set.pop()
                batch.append(device_id)
                self._in_flight.add(device_id)

            if not pending_set:
                del self._pending[priority]

            if len(batch) >= self._batch_size:
                break

        return batch

    async def _execute_batch(self, device_ids: List[str]) -> None:
        """Execute batch and resolve waiting futures."""
        self._stats["batches_executed"] += 1

        try:
            # This should be overridden or injected
            result = await self._fetch_batch(device_ids)

            # Resolve waiting futures
            resolved_waiters = []

            for waiting_ids, future in self._waiters:
                # Check if any of the waiting IDs were in this batch
                if waiting_ids & set(device_ids):
                    if not future.done():
                        # Filter result to only include requested devices
                        filtered_result = SyncLatestStatusResult(
                            devices={k: v for k, v in result.devices.items() if k in waiting_ids},
                            count=len([k for k in result.devices if k in waiting_ids]),
                            timestamp=result.timestamp,
                        )
                        future.set_result(filtered_result)
                    resolved_waiters.append((waiting_ids, future))

            # Remove resolved waiters
            for waiter in resolved_waiters:
                self._waiters.remove(waiter)

        except Exception as e:
            logger.error(f"[BatchManager] Batch execution failed: {e}")

            # Reject waiting futures
            for waiting_ids, future in self._waiters:
                if waiting_ids & set(device_ids):
                    if not future.done():
                        future.set_exception(e)

        finally:
            # Remove from in-flight
            async with self._lock:
                self._in_flight -= set(device_ids)

    async def _fetch_batch(self, device_ids: List[str]) -> SyncLatestStatusResult:
        """
        Fetch data for batch. Override or inject implementation.
        """
        raise NotImplementedError("Override _fetch_batch or inject implementation")

    def get_stats(self) -> Dict[str, Any]:
        """Get batch manager statistics."""
        return {
            **self._stats,
            "pending_count": sum(len(s) for s in self._pending.values()),
            "in_flight_count": len(self._in_flight),
            "waiting_futures": len(self._waiters),
        }


# =============================================================================
# Parallel Chunk Processor
# =============================================================================


class ParallelChunkProcessor:
    """
    Process large device lists in parallel chunks.

    Optimizes large batch operations by:
    - Splitting into optimal chunk sizes
    - Processing chunks concurrently
    - Aggregating results progressively
    - Handling partial failures gracefully
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        max_concurrent: int = MAX_CONCURRENT_BATCHES,
    ):
        self._chunk_size = chunk_size
        self._max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def process(
        self,
        device_ids: List[str],
        process_func: Callable[[List[str]], Any],
    ) -> List[Any]:
        """
        Process devices in parallel chunks.

        Args:
            device_ids: All device IDs to process
            process_func: Async function to process each chunk

        Returns:
            List of results from all successful chunks
        """
        if not device_ids:
            return []

        # Create semaphore for concurrency control
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)

        # Split into chunks
        chunks = [device_ids[i : i + self._chunk_size] for i in range(0, len(device_ids), self._chunk_size)]

        logger.debug(f"[ParallelProcessor] Processing {len(device_ids)} devices " f"in {len(chunks)} chunks")

        # Process all chunks
        async def process_with_semaphore(chunk: List[str], index: int):
            async with self._semaphore:
                try:
                    return await process_func(chunk)
                except Exception as e:
                    logger.warning(f"[ParallelProcessor] Chunk {index} failed: {e}")
                    return None

        results = await asyncio.gather(*[process_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)])

        # Filter successful results
        valid_results = [r for r in results if r is not None]

        logger.debug(f"[ParallelProcessor] Completed: " f"{len(valid_results)}/{len(chunks)} chunks successful")

        return valid_results

    async def process_progressive(
        self,
        device_ids: List[str],
        process_func: Callable[[List[str]], Any],
    ) -> AsyncGenerator[Any, None]:
        """
        Process chunks and yield results as they complete.

        Use this for progressive UI updates.
        """
        if not device_ids:
            return

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)

        chunks = [device_ids[i : i + self._chunk_size] for i in range(0, len(device_ids), self._chunk_size)]

        async def process_with_semaphore(chunk: List[str]):
            async with self._semaphore:
                return await process_func(chunk)

        # Create tasks
        tasks = [asyncio.create_task(process_with_semaphore(chunk)) for chunk in chunks]

        # Yield results as they complete
        for completed in asyncio.as_completed(tasks):
            try:
                result = await completed
                yield result
            except Exception as e:
                logger.warning(f"[ParallelProcessor] Chunk error: {e}")


# =============================================================================
# Optimized Sync Handlers
# =============================================================================


class SyncLatestStatusHandler:
    """
    Optimized handler for syncing latest device status.

    Features:
    - Batch fetching
    - Bulk repository operations
    - Memory-efficient processing
    - Result caching
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
        enable_batching: bool = True,
        enable_caching: bool = True,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._enable_batching = enable_batching
        self._enable_caching = enable_caching

        # Batch manager
        self._batch_manager: Optional[BatchRequestManager] = None
        if enable_batching:
            self._batch_manager = BatchRequestManager()
            self._batch_manager._fetch_batch = self._fetch_batch_internal

        # Chunk processor
        self._chunk_processor = ParallelChunkProcessor()

        # Result cache
        self._cache: Dict[str, Tuple[SyncedDeviceData, float]] = {}

    async def execute(self, request: SyncLatestStatusRequest) -> SyncLatestStatusResult:
        """Execute sync with optimizations."""
        if not request.device_ids:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        start_time = time.time()
        device_ids = list(request.device_ids)

        # Check cache first
        cached_results: Dict[str, SyncedDeviceData] = {}
        uncached_ids: List[str] = []

        if self._enable_caching and not request.skip_cache:
            cached_results, uncached_ids = self._check_cache(device_ids)

            if not uncached_ids:
                # All from cache
                duration = (time.time() - start_time) * 1000
                return SyncLatestStatusResult(
                    devices=cached_results,
                    count=len(cached_results),
                    timestamp=datetime.now(),
                    from_cache=True,
                    duration_ms=duration,
                )
        else:
            uncached_ids = device_ids

        # Use batch manager if enabled
        if self._batch_manager and self._enable_batching:
            try:
                future = await self._batch_manager.add_request(uncached_ids, request.priority)
                result = await future

                # Merge with cached
                if cached_results:
                    result.devices.update(cached_results)
                    result.count = len(result.devices)

                result.duration_ms = (time.time() - start_time) * 1000
                return result

            except Exception as e:
                logger.error(f"[SyncHandler] Batch execution failed: {e}")
                return SyncLatestStatusResult(error=str(e))

        # Direct execution
        try:
            result = await self._fetch_batch_internal(uncached_ids)

            # Merge with cached
            if cached_results:
                result.devices.update(cached_results)
                result.count = len(result.devices)

            # Persist to database
            await self._persist_devices(result.devices)

            result.duration_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            logger.error(f"[SyncHandler] Execution failed: {e}")
            return SyncLatestStatusResult(error=str(e))

    async def _fetch_batch_internal(self, device_ids: List[str]) -> SyncLatestStatusResult:
        """Internal batch fetch implementation."""
        # Convert to remote IDs
        remote_ids = self._id_mapper.to_remote_ids(device_ids)

        logger.debug(f"[SyncHandler] Fetching {len(remote_ids)} devices")

        # Fetch from remote
        records = await self._remote_source.fetch_latest_status(remote_ids)

        if not records:
            return SyncLatestStatusResult(count=0, timestamp=datetime.now())

        # Process records
        devices: Dict[str, SyncedDeviceData] = {}

        for record in records:
            remote_code = record.get("equip_code", "")
            if not remote_code:
                continue

            display_code = self._id_mapper.to_display_id(remote_code)

            raw_status = record.get("raw_status") or record.get("equip_status", 0)
            try:
                status_code = int(raw_status)
            except (ValueError, TypeError):
                status_code = 0

            device_data = SyncedDeviceData(
                equip_code=display_code,
                status_code=status_code,
                status_name=MachineStatus(status_code).name if status_code in [s.value for s in MachineStatus] else "UNKNOWN",
                last_update=record.get("last_update"),
                equip_name=record.get("equip_name"),
                is_active=True,
            )

            devices[display_code] = device_data

            # Update cache
            if self._enable_caching:
                self._cache[display_code] = (device_data, time.time())

        return SyncLatestStatusResult(
            devices=devices,
            count=len(devices),
            timestamp=datetime.now(),
        )

    def _check_cache(self, device_ids: List[str]) -> Tuple[Dict[str, SyncedDeviceData], List[str]]:
        """Check cache for devices."""
        current_time = time.time()
        cached: Dict[str, SyncedDeviceData] = {}
        uncached: List[str] = []

        for device_id in device_ids:
            if device_id in self._cache:
                data, timestamp = self._cache[device_id]
                if current_time - timestamp < CACHE_TTL_SECONDS:
                    cached[device_id] = data
                    continue

            uncached.append(device_id)

        return cached, uncached

    async def _persist_devices(self, devices: Dict[str, SyncedDeviceData]) -> None:
        """Bulk persist devices to database."""
        if not devices:
            return

        try:
            async with self._uow_factory() as uow:
                if not uow.devices:
                    return

                # Pre-load existing devices
                existing: Dict[str, Device] = {}

                try:
                    all_devices = await uow.devices.get_all()
                    existing = {d.equipment_code.value.upper(): d for d in all_devices}
                except Exception as e:
                    logger.warning(f"[SyncHandler] Pre-load failed: {e}")

                # Prepare batch
                to_save: List[Device] = []

                for code, data in devices.items():
                    code_upper = code.upper()

                    try:
                        status_enum = MachineStatus(data.status_code)
                    except ValueError:
                        status_enum = MachineStatus.UNKNOWN

                    if code_upper in existing:
                        device = existing[code_upper]
                        if device.sync_status(status_enum, data.last_update):
                            device.update_remote_info(data.equip_name, None)
                            to_save.append(device)
                    else:
                        device = Device(
                            equipment_code=EquipmentCode(code),
                            current_status=status_enum,
                            last_updated_at=data.last_update or datetime.now(),
                            equip_name=data.equip_name,
                        )
                        to_save.append(device)

                # Bulk save
                if to_save:
                    if hasattr(uow.devices, "bulk_save"):
                        await uow.devices.bulk_save(to_save)
                    else:
                        for device in to_save:
                            await uow.devices.save(device)

                await uow.commit()

                logger.debug(f"[SyncHandler] Persisted {len(to_save)} devices")

        except Exception as e:
            logger.error(f"[SyncHandler] Persist failed: {e}")

    def clear_cache(self) -> None:
        """Clear result cache."""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        stats = {
            "cache_size": len(self._cache),
            "caching_enabled": self._enable_caching,
            "batching_enabled": self._enable_batching,
        }

        if self._batch_manager:
            stats["batch_manager"] = self._batch_manager.get_stats()

        return stats


class SyncHistoryHandler:
    """Optimized handler for history sync."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._chunk_processor = ParallelChunkProcessor()

    async def execute(self, request: SyncHistoryRequest) -> SyncHistoryResult:
        """Execute history sync with parallel processing."""
        if not request.device_ids:
            return SyncHistoryResult()

        start_time = time.time()
        device_ids = list(request.device_ids)

        total_synced = 0
        devices_processed = 0
        all_periods: List[StatusPeriod] = []

        # Process in parallel chunks
        async def fetch_device_history(chunk: List[str]) -> List[StatusPeriod]:
            chunk_periods = []

            for display_id in chunk:
                remote_id = self._id_mapper.to_remote_id(display_id)

                try:
                    records = await self._remote_source.fetch_device_history_range(remote_id, request.start_time, request.end_time)

                    if records:
                        periods = self._convert_to_periods(display_id, records)
                        chunk_periods.extend(periods)

                except Exception as e:
                    logger.warning(f"[HistoryHandler] Fetch failed for {display_id}: {e}")

            return chunk_periods

        # Execute parallel chunks
        results = await self._chunk_processor.process(device_ids, fetch_device_history)

        # Aggregate results
        for chunk_periods in results:
            all_periods.extend(chunk_periods)

        # Bulk save
        if all_periods:
            try:
                async with self._uow_factory() as uow:
                    if uow.history:
                        await uow.history.bulk_save_status_history(all_periods)
                    await uow.commit()

                total_synced = len(all_periods)
                devices_processed = len(set(p.equipment_code.value for p in all_periods))

            except Exception as e:
                logger.error(f"[HistoryHandler] Bulk save failed: {e}")
                return SyncHistoryResult(error=str(e))

        duration = (time.time() - start_time) * 1000

        logger.info(f"[HistoryHandler] Synced {total_synced} records " f"for {devices_processed} devices in {duration:.0f}ms")

        return SyncHistoryResult(
            records_synced=total_synced,
            devices_processed=devices_processed,
            duration_ms=duration,
        )

    def _convert_to_periods(self, display_code: str, records: List[Dict[str, Any]]) -> List[StatusPeriod]:
        """Convert records to StatusPeriod objects."""
        periods = []

        for record in records:
            start_time = record.get("start_time")
            if not start_time:
                continue

            raw_status = record.get("equip_status", 0)
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

        return periods


class SyncIncrementalHistoryHandler:
    """Optimized handler for incremental history sync."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._remote_source = remote_source
        self._uow_factory = uow_factory
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._chunk_processor = ParallelChunkProcessor()

    async def execute(self, request: SyncIncrementalRequest) -> SyncHistoryResult:
        """Execute incremental sync."""
        if not request.device_ids:
            return SyncHistoryResult()

        start_time = time.time()
        device_ids = list(request.device_ids)

        all_periods: List[StatusPeriod] = []

        async def fetch_recent(chunk: List[str]) -> List[StatusPeriod]:
            chunk_periods = []

            for display_id in chunk:
                remote_id = self._id_mapper.to_remote_id(display_id)

                try:
                    records = await self._remote_source.fetch_latest_history_records(remote_id, limit=request.record_limit)

                    if records:
                        periods = self._convert_to_periods(display_id, records)
                        chunk_periods.extend(periods)

                except Exception as e:
                    logger.debug(f"[IncrementalHandler] Fetch failed for {display_id}: {e}")

            return chunk_periods

        results = await self._chunk_processor.process(device_ids, fetch_recent)

        for chunk_periods in results:
            all_periods.extend(chunk_periods)

        if all_periods:
            try:
                async with self._uow_factory() as uow:
                    if uow.history:
                        if hasattr(uow.history, "bulk_upsert_status_periods"):
                            await uow.history.bulk_upsert_status_periods(all_periods)
                        else:
                            for period in all_periods:
                                await uow.history.save_status_period(period)
                    await uow.commit()

            except Exception as e:
                logger.error(f"[IncrementalHandler] Bulk upsert failed: {e}")
                return SyncHistoryResult(error=str(e))

        duration = (time.time() - start_time) * 1000

        return SyncHistoryResult(
            records_synced=len(all_periods),
            devices_processed=len(set(p.equipment_code.value for p in all_periods)),
            duration_ms=duration,
        )

    def _convert_to_periods(self, display_code: str, records: List[Dict[str, Any]]) -> List[StatusPeriod]:
        """Convert records to StatusPeriod objects."""
        periods = []

        for record in records:
            start_time = record.get("start_time")
            if not start_time:
                continue

            raw_status = record.get("equip_status", 0)
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

        return periods


# =============================================================================
# Legacy Compatibility Wrappers
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
        request = SyncLatestStatusRequest.from_list(equipment_codes)
        result = await self._handler.execute(request)

        return {
            "devices": {k: v.to_dict() for k, v in result.devices.items()},
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

        request = SyncHistoryRequest.from_list(equipment_codes, start, end)
        result = await self._handler.execute(request)
        return result.records_synced


class SyncIncrementalHistoryCommand:
    """DEPRECATED: Use SyncIncrementalHistoryHandler."""

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
        id_mapper: Optional[IDeviceIdMapper] = None,
    ):
        self._handler = SyncIncrementalHistoryHandler(remote_source, dual_uow_factory, id_mapper)

    async def execute(self, equipment_codes: List[str]) -> int:
        request = SyncIncrementalRequest.from_list(equipment_codes)
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
        request = SyncLatestStatusRequest.from_list(equipment_codes or [])
        result = await self._handler.execute(request)
        return result.count


class SyncDeviceStatusCommand:
    """Handler for single device history sync."""

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
        """Sync history for a single device."""
        try:
            now = datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

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

                raw_status = record.get("equip_status", 0)
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

            async with self._uow as uow:
                if uow.history and periods:
                    await uow.history.bulk_save_status_history(periods, equip_name=equip_name)
                await uow.commit()

            logger.info(f"[SyncDeviceStatus] Synced {len(data)} records for {equip_code}")
            return True

        except Exception as e:
            logger.error(f"[SyncDeviceStatus] Failed for {equip_code}: {e}")
            return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Protocols
    "IDeviceIdMapper",
    "NoOpIdMapper",
    # Request/Response (Memory-Optimized)
    "SyncLatestStatusRequest",
    "SyncHistoryRequest",
    "SyncIncrementalRequest",
    "SyncLatestStatusResult",
    "SyncHistoryResult",
    "SyncedDeviceData",
    # Handlers (Optimized)
    "SyncLatestStatusHandler",
    "SyncHistoryHandler",
    "SyncIncrementalHistoryHandler",
    # Batch Processing
    "BatchRequestManager",
    "ParallelChunkProcessor",
    # Legacy (Deprecated)
    "SyncLatestStatusCommand",
    "SyncInitialHistoryCommand",
    "SyncIncrementalHistoryCommand",
    "SyncAllDevicesCommand",
    "SyncDeviceStatusCommand",
]
