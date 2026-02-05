# src/iFactory/presentation/services/progressive_loader.py
"""
Progressive Device Loader - Orchestrates multi-stage loading.

Implements the progressive loading pattern:
    Stage 1 (T+0ms):    SKELETON - Immediate placeholder
    Stage 2 (T+20-30ms): STALE - Cached data from memory
    Stage 3 (T+150-200ms): FRESH - Fresh data from remote
    Stage 4 (T+300ms+):   LIVE - Real-time subscriptions

Usage:
    loader = ProgressiveDeviceLoader(
        swr_service=swr,
        device_service=device_service,
        status_service=status_service,
    )

    # Load single device through all stages
    await loader.load_device("DEV01", priority=LoadPriority.HIGH)

    # Load batch (e.g., visible devices)
    await loader.load_batch(["DEV01", "DEV02", "DEV03"])

    # Listen to stage changes
    loader.on_stage_changed(lambda id, stage, data: print(f"{id} -> {stage}"))
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from iFactory.application.services.swr_service import SWRService
    from iFactory.presentation.services.device_status_service import DeviceStatusService

logger = logging.getLogger(__name__)


# ============================================================================
# Loading Stages
# ============================================================================


class LoadingStage(Enum):
    """Progressive loading stages."""

    SKELETON = "skeleton"  # T+0ms - Immediate placeholder
    STALE = "stale"  # T+20-30ms - Cached data
    FRESH = "fresh"  # T+150-200ms - Fresh from remote
    LIVE = "live"  # T+300ms+ - Real-time updates
    ERROR = "error"  # Error state


class LoadPriority(Enum):
    """Loading priority levels."""

    CRITICAL = auto()  # User-triggered, immediate
    HIGH = auto()  # Visible devices
    NORMAL = auto()  # Prefetch zone
    LOW = auto()  # Background


# ============================================================================
# Loading State
# ============================================================================


@dataclass
class LoadingState:
    """State for a loading operation."""

    device_id: str
    stage: LoadingStage
    priority: LoadPriority
    data: Optional[Any] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    stage_times: Dict[LoadingStage, float] = field(default_factory=dict)

    @property
    def is_loading(self) -> bool:
        """Check if still loading."""
        return self.stage in (LoadingStage.SKELETON, LoadingStage.STALE)

    @property
    def is_complete(self) -> bool:
        """Check if loading is complete."""
        return self.stage in (LoadingStage.FRESH, LoadingStage.LIVE, LoadingStage.ERROR)

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (datetime.now() - self.started_at).total_seconds() * 1000

    def record_stage_time(self, stage: LoadingStage) -> None:
        """Record timing for a stage."""
        self.stage_times[stage] = self.elapsed_ms


@dataclass
class LoadingMetrics:
    """Metrics for progressive loading."""

    total_loads: int = 0
    skeleton_count: int = 0
    stale_served: int = 0
    fresh_fetched: int = 0
    live_started: int = 0
    errors: int = 0

    # Timing stats
    total_skeleton_time_ms: float = 0.0
    total_stale_time_ms: float = 0.0
    total_fresh_time_ms: float = 0.0

    @property
    def avg_skeleton_time_ms(self) -> float:
        return self.total_skeleton_time_ms / self.skeleton_count if self.skeleton_count > 0 else 0.0

    @property
    def avg_stale_time_ms(self) -> float:
        return self.total_stale_time_ms / self.stale_served if self.stale_served > 0 else 0.0

    @property
    def avg_fresh_time_ms(self) -> float:
        return self.total_fresh_time_ms / self.fresh_fetched if self.fresh_fetched > 0 else 0.0

    @property
    def stale_hit_rate(self) -> float:
        """Percentage of loads served from stale cache."""
        return (self.stale_served / self.total_loads * 100) if self.total_loads > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_loads": self.total_loads,
            "stale_served": self.stale_served,
            "fresh_fetched": self.fresh_fetched,
            "live_started": self.live_started,
            "errors": self.errors,
            "stale_hit_rate": f"{self.stale_hit_rate:.1f}%",
            "avg_skeleton_ms": f"{self.avg_skeleton_time_ms:.1f}",
            "avg_stale_ms": f"{self.avg_stale_time_ms:.1f}",
            "avg_fresh_ms": f"{self.avg_fresh_time_ms:.1f}",
        }


# ============================================================================
# Progressive Device Loader
# ============================================================================


class ProgressiveDeviceLoader:
    """
    Orchestrates progressive device loading through multiple stages.

    Features:
    - 4-stage loading (skeleton → stale → fresh → live)
    - Priority-based scheduling
    - Parallel loading with concurrency control
    - Stage timing tracking
    - Callbacks for UI updates
    - Request deduplication

    Timeline for single device:
        T+0ms:    emit(SKELETON, None)
        T+30ms:   emit(STALE, cached_data) if available
        T+150ms:  emit(FRESH, fresh_data) from remote
        T+300ms:  emit(LIVE, subscription_id)

    Usage:
        loader = ProgressiveDeviceLoader(...)

        # Single device
        await loader.load_device("DEV01")

        # Batch (visible devices)
        await loader.load_batch(visible_ids, priority=LoadPriority.HIGH)

        # Listen to updates
        loader.on_stage_changed(update_ui)
    """

    def __init__(
        self,
        swr_service: SWRService,
        device_service: Any,  # Service to fetch device data
        status_service: Optional[DeviceStatusService] = None,
        max_concurrent_loads: int = 10,
    ):
        self._swr_service = swr_service
        self._device_service = device_service
        self._status_service = status_service
        self._max_concurrent = max_concurrent_loads

        # State tracking
        self._loading_states: Dict[str, LoadingState] = {}
        self._active_loads: Set[str] = set()
        self._load_lock = asyncio.Lock()

        # Concurrency control
        self._load_semaphore = asyncio.Semaphore(max_concurrent_loads)

        # Callbacks
        self._stage_callbacks: List[Callable[[str, LoadingStage, Any], None]] = []

        # Metrics
        self._metrics = LoadingMetrics()

        logger.info(
            "[ProgressiveLoader] Initialized with max_concurrent=%d",
            max_concurrent_loads,
        )

    # ========================================================================
    # Public API: Single Device Loading
    # ========================================================================

    async def load_device(
        self,
        device_id: str,
        priority: LoadPriority = LoadPriority.NORMAL,
        force_fresh: bool = False,
    ) -> None:
        """
        Load a single device through all progressive stages.

        Args:
            device_id: Device to load
            priority: Loading priority
            force_fresh: Skip stale and fetch fresh immediately

        Timeline:
            T+0ms:    SKELETON emitted
            T+30ms:   STALE emitted (if cached)
            T+150ms:  FRESH emitted
            T+300ms:  LIVE subscription started
        """
        # Check if already loading
        async with self._load_lock:
            if device_id in self._active_loads:
                logger.debug(f"[ProgressiveLoader] Already loading: {device_id}")
                return

            self._active_loads.add(device_id)

            # Create loading state
            state = LoadingState(
                device_id=device_id,
                stage=LoadingStage.SKELETON,
                priority=priority,
            )
            self._loading_states[device_id] = state

        try:
            await self._execute_progressive_load(device_id, priority, force_fresh)
        finally:
            async with self._load_lock:
                self._active_loads.discard(device_id)

    async def _execute_progressive_load(
        self,
        device_id: str,
        priority: LoadPriority,
        force_fresh: bool,
    ) -> None:
        """Execute the progressive loading stages."""
        state = self._loading_states[device_id]

        # Stage 1: SKELETON (T+0ms)
        await self._emit_skeleton(device_id, state)

        if force_fresh:
            # Skip stale, go directly to fresh
            await self._load_fresh(device_id, state)
        else:
            # Stage 2 & 3: STALE → FRESH (with SWR)
            await self._load_with_swr(device_id, state)

        # Stage 4: LIVE (T+300ms)
        if state.stage != LoadingStage.ERROR:
            await self._start_live_updates(device_id, state)

    # ========================================================================
    # Public API: Batch Loading
    # ========================================================================

    async def load_batch(
        self,
        device_ids: List[str],
        priority: LoadPriority = LoadPriority.NORMAL,
        force_fresh: bool = False,
    ) -> None:
        """
        Load multiple devices in parallel.

        Args:
            device_ids: Devices to load
            priority: Loading priority
            force_fresh: Skip stale cache

        Features:
        - Parallel loading with concurrency control
        - All skeletons emitted immediately
        - Respects max_concurrent_loads limit
        """
        if not device_ids:
            return

        logger.info(f"[ProgressiveLoader] Batch loading {len(device_ids)} devices " f"(priority={priority.name})")

        # Emit all skeletons first (immediate)
        for device_id in device_ids:
            async with self._load_lock:
                if device_id not in self._loading_states:
                    state = LoadingState(
                        device_id=device_id,
                        stage=LoadingStage.SKELETON,
                        priority=priority,
                    )
                    self._loading_states[device_id] = state
                    await self._emit_skeleton(device_id, state)

        # Load in parallel with semaphore
        tasks = [self._load_device_controlled(device_id, priority, force_fresh) for device_id in device_ids]

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.debug(f"[ProgressiveLoader] Batch complete: {len(device_ids)} devices")

    async def _load_device_controlled(
        self,
        device_id: str,
        priority: LoadPriority,
        force_fresh: bool,
    ) -> None:
        """Load device with concurrency control."""
        async with self._load_semaphore:
            try:
                async with self._load_lock:
                    if device_id in self._active_loads:
                        return
                    self._active_loads.add(device_id)

                await self._execute_progressive_load(device_id, priority, force_fresh)

            except Exception as e:
                logger.error(f"[ProgressiveLoader] Load error for {device_id}: {e}")
                await self._emit_error(device_id, str(e))

            finally:
                async with self._load_lock:
                    self._active_loads.discard(device_id)

    # ========================================================================
    # Stage Implementation
    # ========================================================================

    async def _emit_skeleton(
        self,
        device_id: str,
        state: LoadingState,
    ) -> None:
        """
        Stage 1: Emit skeleton placeholder.

        Target: T+0ms (immediate)
        """
        state.stage = LoadingStage.SKELETON
        state.record_stage_time(LoadingStage.SKELETON)

        self._metrics.total_loads += 1
        self._metrics.skeleton_count += 1
        self._metrics.total_skeleton_time_ms += state.elapsed_ms

        self._emit_stage(device_id, LoadingStage.SKELETON, None)

    async def _load_with_swr(
        self,
        device_id: str,
        state: LoadingState,
    ) -> None:
        """
        Stage 2 & 3: Load with Stale-While-Revalidate.

        Timeline:
        - T+20-30ms: Emit stale if cached
        - T+150-200ms: Emit fresh after fetch
        """
        cache_key = f"device:{device_id}"

        try:
            # Use SWR to get data
            data, is_fresh = await self._swr_service.get_with_swr(
                cache_key,
                factory=lambda: self._fetch_device_data(device_id),
            )

            if data is None:
                await self._emit_error(device_id, "No data available")
                return

            # Determine stage
            if is_fresh:
                # Fresh data (either from cache or just fetched)
                state.stage = LoadingStage.FRESH
                state.record_stage_time(LoadingStage.FRESH)

                self._metrics.fresh_fetched += 1
                self._metrics.total_fresh_time_ms += state.elapsed_ms

                self._emit_stage(device_id, LoadingStage.FRESH, data)
            else:
                # Stale data (background refresh triggered)
                state.stage = LoadingStage.STALE
                state.record_stage_time(LoadingStage.STALE)

                self._metrics.stale_served += 1
                self._metrics.total_stale_time_ms += state.elapsed_ms

                self._emit_stage(device_id, LoadingStage.STALE, data)

                # Note: Fresh data will arrive via background refresh
                # and will be emitted through status service updates

        except Exception as e:
            logger.error(f"[ProgressiveLoader] SWR error for {device_id}: {e}")
            await self._emit_error(device_id, str(e))

    async def _load_fresh(
        self,
        device_id: str,
        state: LoadingState,
    ) -> None:
        """
        Stage 3: Load fresh data directly (bypass stale).

        Target: T+150-200ms
        """
        try:
            data = await self._fetch_device_data(device_id)

            if data is None:
                await self._emit_error(device_id, "No data available")
                return

            state.stage = LoadingStage.FRESH
            state.record_stage_time(LoadingStage.FRESH)

            self._metrics.fresh_fetched += 1
            self._metrics.total_fresh_time_ms += state.elapsed_ms

            self._emit_stage(device_id, LoadingStage.FRESH, data)

            # Cache for future SWR
            cache_key = f"device:{device_id}"
            await self._swr_service._cache.set(cache_key, data, ttl=300)

        except Exception as e:
            logger.error(f"[ProgressiveLoader] Fresh fetch error for {device_id}: {e}")
            await self._emit_error(device_id, str(e))

    async def _start_live_updates(
        self,
        device_id: str,
        state: LoadingState,
    ) -> None:
        """
        Stage 4: Start live updates subscription.

        Target: T+300ms+
        """
        # Small delay to avoid overwhelming the system
        await asyncio.sleep(0.1)

        state.stage = LoadingStage.LIVE
        state.record_stage_time(LoadingStage.LIVE)

        self._metrics.live_started += 1

        self._emit_stage(device_id, LoadingStage.LIVE, None)

        logger.debug(f"[ProgressiveLoader] Live updates started for {device_id} " f"(total time: {state.elapsed_ms:.0f}ms)")

    async def _emit_error(self, device_id: str, error: str) -> None:
        """Emit error stage."""
        state = self._loading_states.get(device_id)
        if state:
            state.stage = LoadingStage.ERROR
            state.error = error
            self._metrics.errors += 1

        self._emit_stage(device_id, LoadingStage.ERROR, None)

    # ========================================================================
    # Data Fetching
    # ========================================================================

    async def _fetch_device_data(self, device_id: str) -> Optional[Any]:
        """
        Fetch fresh device data from service.

        This is the factory function for SWR.
        Override this method to customize data fetching.
        """
        if not self._device_service:
            return None

        try:
            # If device service has async method
            if hasattr(self._device_service, "fetch_device_async"):
                return await self._device_service.fetch_device_async(device_id)

            # If device service has sync method (run in executor)
            if hasattr(self._device_service, "fetch_device"):
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    self._device_service.fetch_device,
                    device_id,
                )

            # Fallback: Get from status service
            if self._status_service:
                return self._status_service.get_device_status(device_id)

            return None

        except Exception as e:
            logger.error(f"[ProgressiveLoader] Fetch failed for {device_id}: {e}")
            return None

    # ========================================================================
    # Stage Emission
    # ========================================================================

    def _emit_stage(
        self,
        device_id: str,
        stage: LoadingStage,
        data: Optional[Any],
    ) -> None:
        """
        Emit stage change to all registered callbacks.

        Callbacks receive:
        - device_id: str
        - stage: LoadingStage
        - data: Optional[Any]
        """
        for callback in self._stage_callbacks:
            try:
                callback(device_id, stage, data)
            except Exception as e:
                logger.error(f"[ProgressiveLoader] Callback error: {e}")

    # ========================================================================
    # Callbacks
    # ========================================================================

    def on_stage_changed(
        self,
        callback: Callable[[str, LoadingStage, Any], None],
    ) -> None:
        """
        Register callback for stage changes.

        Args:
            callback: Function(device_id, stage, data) -> None

        Example:
            def update_ui(device_id, stage, data):
                if stage == LoadingStage.SKELETON:
                    show_skeleton(device_id)
                elif stage == LoadingStage.STALE:
                    render_device(device_id, data, is_stale=True)
                elif stage == LoadingStage.FRESH:
                    render_device(device_id, data, is_stale=False)

            loader.on_stage_changed(update_ui)
        """
        self._stage_callbacks.append(callback)

    # ========================================================================
    # Control Methods
    # ========================================================================

    async def cancel_load(self, device_id: str) -> bool:
        """
        Cancel an in-progress load.

        Returns:
            True if load was cancelled
        """
        async with self._load_lock:
            if device_id in self._active_loads:
                self._active_loads.discard(device_id)
                self._loading_states.pop(device_id, None)
                logger.debug(f"[ProgressiveLoader] Cancelled load: {device_id}")
                return True
            return False

    async def cancel_all(self) -> int:
        """
        Cancel all in-progress loads.

        Returns:
            Number of loads cancelled
        """
        async with self._load_lock:
            count = len(self._active_loads)
            self._active_loads.clear()
            self._loading_states.clear()
            logger.info(f"[ProgressiveLoader] Cancelled {count} loads")
            return count

    def is_loading(self, device_id: str) -> bool:
        """Check if device is currently loading."""
        state = self._loading_states.get(device_id)
        return state.is_loading if state else False

    def get_loading_stage(self, device_id: str) -> Optional[LoadingStage]:
        """Get current loading stage for device."""
        state = self._loading_states.get(device_id)
        return state.stage if state else None

    # ========================================================================
    # Metrics
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get loading metrics."""
        return {
            **self._metrics.to_dict(),
            "active_loads": len(self._active_loads),
            "max_concurrent": self._max_concurrent,
        }

    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics = LoadingMetrics()

    def get_loading_states(self) -> Dict[str, LoadingState]:
        """Get all current loading states (for debugging)."""
        return self._loading_states.copy()


__all__ = [
    "ProgressiveDeviceLoader",
    "LoadingStage",
    "LoadPriority",
    "LoadingState",
    "LoadingMetrics",
]
