# src/iFactory/presentation/di/container.py
"""
Enhanced UI Dependency Injection Container.

OPTIMIZATION CONCEPTS IMPLEMENTED:
1. UI Virtualization Support - Viewport-aware refresh
2. Predictive Prefetching - Anticipate user navigation
3. Progressive Loading - Priority-based loading queue
4. Smart Auto-Refresh - Adaptive intervals with pause/resume
5. Memory Management - Weak references, cleanup cycles

Version: 2.0
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Deque,
    Dict,
    FrozenSet,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)
from weakref import WeakSet, WeakValueDictionary, ref

from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter
    from ..services.page_device_manager import PageDeviceManager
    from ..services.theme_service import ThemeService
    from ..services.icon_service import IconService
    from ..state.store import Store
    from ..viewmodels import (
        DeviceListViewModel,
        GanttChartViewModel,
        ShellViewModel,
    )
    from ..views.main_window import MainWindow

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Constants
# ============================================================================

# Refresh intervals
REFRESH_INTERVAL_ACTIVE_MS = 3000
REFRESH_INTERVAL_IDLE_MS = 10000
REFRESH_INTERVAL_BACKGROUND_MS = 30000

# Prefetching
PREFETCH_DELAY_MS = 500
PREFETCH_MAX_ITEMS = 20

# Progressive loading
PROGRESSIVE_BATCH_SIZE = 10
PROGRESSIVE_BATCH_DELAY_MS = 50

# Memory management
CLEANUP_INTERVAL_TICKS = 20
MAX_CACHED_PAGES = 5


# ============================================================================
# Configuration
# ============================================================================


@dataclass(frozen=True)
class UIContainerConfig:
    """
    Immutable configuration for UIContainer.

    Using frozen=True for thread safety and hashability.
    """

    # Auto-refresh settings
    auto_refresh_interval_ms: int = REFRESH_INTERVAL_ACTIVE_MS
    adaptive_refresh: bool = True
    refresh_interval_active_ms: int = REFRESH_INTERVAL_ACTIVE_MS
    refresh_interval_idle_ms: int = REFRESH_INTERVAL_IDLE_MS
    refresh_interval_background_ms: int = REFRESH_INTERVAL_BACKGROUND_MS
    pause_on_unfocus: bool = True
    idle_timeout_ms: int = 30000

    # Progressive loading
    enable_progressive_loading: bool = True
    progressive_batch_size: int = PROGRESSIVE_BATCH_SIZE
    progressive_batch_delay_ms: int = PROGRESSIVE_BATCH_DELAY_MS

    # Prefetching
    enable_prefetching: bool = True
    prefetch_delay_ms: int = PREFETCH_DELAY_MS
    prefetch_max_items: int = PREFETCH_MAX_ITEMS

    # Virtualization
    enable_virtualization: bool = True
    viewport_buffer_ratio: float = 0.5  # Extra buffer around viewport

    # General
    deferred_load_delay_ms: int = 100
    preload_icons: bool = True
    enable_time_travel: bool = False
    persist_state: bool = False
    state_persistence_path: Optional[str] = None


# ============================================================================
# Protocols
# ============================================================================


class IRemoteSource(Protocol):
    """Protocol for remote data source."""

    async def fetch_device_status(self, device_ids: list) -> dict: ...


class IViewportProvider(Protocol):
    """Protocol for components that can provide visible device info."""

    def get_visible_device_ids(self) -> List[str]: ...
    def get_viewport_bounds(self) -> Tuple[float, float, float, float]: ...


class INavigationPredictor(Protocol):
    """Protocol for navigation prediction."""

    def predict_next_page(self, current_page: str) -> Optional[str]: ...
    def get_adjacent_pages(self, current_page: str) -> List[str]: ...


# ============================================================================
# Loading Priority
# ============================================================================


class LoadPriority(IntEnum):
    """Priority levels for progressive loading."""

    CRITICAL = 0  # Currently visible, selected
    HIGH = 1  # In viewport buffer
    NORMAL = 2  # On current page
    LOW = 3  # Prefetched pages
    BACKGROUND = 4  # Everything else


@dataclass(slots=True)
class LoadRequest:
    """
    Memory-efficient load request using __slots__.

    Represents a single device load request with priority.
    """

    device_id: str
    priority: LoadPriority
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0

    def __lt__(self, other: "LoadRequest") -> bool:
        """Compare by priority then timestamp for heap ordering."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __hash__(self) -> int:
        return hash(self.device_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LoadRequest):
            return self.device_id == other.device_id
        return False


# ============================================================================
# Progressive Loading Queue
# ============================================================================


class ProgressiveLoadQueue:
    """
    Priority queue for progressive device loading.

    Features:
    - Priority-based ordering (visible first)
    - Batch processing with delays
    - Deduplication
    - Memory-efficient storage
    """

    def __init__(
        self,
        batch_size: int = PROGRESSIVE_BATCH_SIZE,
        batch_delay_ms: int = PROGRESSIVE_BATCH_DELAY_MS,
    ):
        self._batch_size = batch_size
        self._batch_delay_ms = batch_delay_ms

        # Use deque for O(1) append/popleft
        self._queues: Dict[LoadPriority, Deque[str]] = {priority: deque() for priority in LoadPriority}

        # Track all pending devices for deduplication
        self._pending: Set[str] = set()

        # Processing state
        self._is_processing = False
        self._process_timer: Optional[QTimer] = None
        self._on_batch_ready: Optional[Callable[[List[str], LoadPriority], None]] = None

        # Stats
        self._total_enqueued = 0
        self._total_processed = 0

    def set_batch_callback(self, callback: Callable[[List[str], LoadPriority], None]) -> None:
        """Set callback for when a batch is ready."""
        self._on_batch_ready = callback

    def enqueue(
        self,
        device_ids: List[str],
        priority: LoadPriority = LoadPriority.NORMAL,
    ) -> int:
        """
        Enqueue devices for loading.

        Returns:
            Number of new devices added (after deduplication)
        """
        added = 0

        for device_id in device_ids:
            if device_id in self._pending:
                continue

            self._pending.add(device_id)
            self._queues[priority].append(device_id)
            added += 1

        self._total_enqueued += added

        if added > 0:
            logger.debug(f"[ProgressiveQueue] Enqueued {added} devices at priority {priority.name}")
            self._start_processing()

        return added

    def enqueue_with_priority_map(
        self,
        priority_map: Dict[LoadPriority, List[str]],
    ) -> int:
        """
        Enqueue devices with different priorities in one call.

        Args:
            priority_map: Dict mapping priority to device IDs

        Returns:
            Total number of new devices added
        """
        total_added = 0

        for priority, device_ids in priority_map.items():
            total_added += self.enqueue(device_ids, priority)

        return total_added

    def promote(self, device_id: str, new_priority: LoadPriority) -> bool:
        """
        Promote a device to higher priority.

        Note: This is O(n) but rarely called.
        """
        if device_id not in self._pending:
            return False

        # Find and remove from current queue
        for priority, queue in self._queues.items():
            if priority <= new_priority:
                continue  # Already at same or higher priority

            try:
                queue.remove(device_id)
                self._queues[new_priority].appendleft(device_id)
                logger.debug(f"[ProgressiveQueue] Promoted {device_id} to {new_priority.name}")
                return True
            except ValueError:
                continue

        return False

    def clear(self) -> None:
        """Clear all queues."""
        for queue in self._queues.values():
            queue.clear()
        self._pending.clear()
        self._stop_processing()

    def _start_processing(self) -> None:
        """Start batch processing timer."""
        if self._is_processing:
            return

        if not self._process_timer:
            self._process_timer = QTimer()
            self._process_timer.timeout.connect(self._process_next_batch)

        self._is_processing = True
        self._process_timer.start(self._batch_delay_ms)

    def _stop_processing(self) -> None:
        """Stop batch processing."""
        self._is_processing = False
        if self._process_timer:
            self._process_timer.stop()

    def _process_next_batch(self) -> None:
        """Process the next batch from highest priority queue."""
        if not self._on_batch_ready:
            self._stop_processing()
            return

        # Find highest priority non-empty queue
        batch: List[str] = []
        batch_priority = LoadPriority.BACKGROUND

        for priority in LoadPriority:
            queue = self._queues[priority]

            while queue and len(batch) < self._batch_size:
                device_id = queue.popleft()
                self._pending.discard(device_id)
                batch.append(device_id)
                batch_priority = priority

            if batch:
                break

        if batch:
            self._total_processed += len(batch)
            logger.debug(f"[ProgressiveQueue] Processing batch: " f"{len(batch)} devices at {batch_priority.name}")
            self._on_batch_ready(batch, batch_priority)

        # Check if more to process
        has_pending = any(queue for queue in self._queues.values())
        if not has_pending:
            self._stop_processing()

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        queue_sizes = {priority.name: len(queue) for priority, queue in self._queues.items()}

        return {
            "total_enqueued": self._total_enqueued,
            "total_processed": self._total_processed,
            "pending": len(self._pending),
            "is_processing": self._is_processing,
            "queues": queue_sizes,
        }


# ============================================================================
# Predictive Prefetcher
# ============================================================================


class PredictivePrefetcher:
    """
    Anticipates user navigation and prefetches data.

    Features:
    - Page transition prediction based on history
    - Adjacent page prefetching
    - Hover-based prefetching
    - Time-based pattern detection
    """

    def __init__(
        self,
        max_prefetch_items: int = PREFETCH_MAX_ITEMS,
        prefetch_delay_ms: int = PREFETCH_DELAY_MS,
    ):
        self._max_items = max_prefetch_items
        self._delay_ms = prefetch_delay_ms

        # Navigation history for prediction
        self._nav_history: Deque[Tuple[str, float]] = deque(maxlen=50)

        # Transition probability matrix
        self._transitions: Dict[str, Dict[str, int]] = {}

        # Prefetch state
        self._prefetch_timer: Optional[QTimer] = None
        self._pending_prefetch: Optional[str] = None
        self._prefetched_pages: Set[str] = set()

        # Callbacks
        self._on_prefetch: Optional[Callable[[str, List[str]], None]] = None

        # Page device mapping (injected)
        self._page_devices: Dict[str, List[str]] = {}

    def set_prefetch_callback(self, callback: Callable[[str, List[str]], None]) -> None:
        """Set callback for prefetch trigger."""
        self._on_prefetch = callback

    def set_page_devices(self, page_devices: Dict[str, List[str]]) -> None:
        """Set page to device mapping."""
        self._page_devices = page_devices

    def record_navigation(self, page_name: str) -> None:
        """
        Record a page navigation event.

        Updates transition probabilities for prediction.
        """
        current_time = time.time()

        # Update transition matrix if we have history
        if self._nav_history:
            prev_page, _ = self._nav_history[-1]
            if prev_page != page_name:
                if prev_page not in self._transitions:
                    self._transitions[prev_page] = {}
                self._transitions[prev_page][page_name] = self._transitions[prev_page].get(page_name, 0) + 1

        # Add to history
        self._nav_history.append((page_name, current_time))

        # Trigger prefetch for predicted pages
        self._schedule_prefetch(page_name)

    def predict_next_page(self, current_page: str) -> Optional[str]:
        """
        Predict the most likely next page.

        Based on transition history.
        """
        if current_page not in self._transitions:
            return None

        transitions = self._transitions[current_page]
        if not transitions:
            return None

        # Return most frequent transition
        return max(transitions, key=transitions.get)

    def get_prefetch_candidates(self, current_page: str) -> List[str]:
        """
        Get list of pages to prefetch.

        Includes predicted next page and adjacent pages.
        """
        candidates: List[str] = []

        # Predicted next page (highest priority)
        predicted = self.predict_next_page(current_page)
        if predicted and predicted not in self._prefetched_pages:
            candidates.append(predicted)

        # Adjacent pages from transition matrix
        if current_page in self._transitions:
            for page, count in sorted(
                self._transitions[current_page].items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]:
                if page not in candidates and page not in self._prefetched_pages:
                    candidates.append(page)

        return candidates[: self._max_items]

    def on_hover_page(self, page_name: str) -> None:
        """
        Handle hover over a page link.

        Triggers delayed prefetch.
        """
        if page_name in self._prefetched_pages:
            return

        self._pending_prefetch = page_name
        self._schedule_prefetch(page_name, delay_ms=self._delay_ms // 2)

    def _schedule_prefetch(self, current_page: str, delay_ms: Optional[int] = None) -> None:
        """Schedule prefetch with delay."""
        if not self._on_prefetch:
            return

        if not self._prefetch_timer:
            self._prefetch_timer = QTimer()
            self._prefetch_timer.setSingleShot(True)
            self._prefetch_timer.timeout.connect(self._execute_prefetch)

        self._pending_prefetch = current_page
        self._prefetch_timer.start(delay_ms or self._delay_ms)

    def _execute_prefetch(self) -> None:
        """Execute prefetch for candidates."""
        if not self._pending_prefetch or not self._on_prefetch:
            return

        candidates = self.get_prefetch_candidates(self._pending_prefetch)

        for page_name in candidates:
            devices = self._page_devices.get(page_name, [])
            if devices:
                # Limit prefetch size
                prefetch_devices = devices[: self._max_items]
                self._on_prefetch(page_name, prefetch_devices)
                self._prefetched_pages.add(page_name)

                logger.debug(f"[Prefetcher] Prefetched {len(prefetch_devices)} " f"devices for page: {page_name}")

    def clear_cache(self) -> None:
        """Clear prefetch cache."""
        self._prefetched_pages.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get prefetcher statistics."""
        return {
            "history_size": len(self._nav_history),
            "transition_pages": len(self._transitions),
            "prefetched_pages": list(self._prefetched_pages),
            "pending": self._pending_prefetch,
        }


# ============================================================================
# Viewport Manager (for UI Virtualization)
# ============================================================================


class ViewportManager:
    """
    Manages viewport-aware rendering and refresh.

    Features:
    - Track visible devices
    - Buffer zone for smooth scrolling
    - Priority adjustment based on visibility
    """

    def __init__(self, buffer_ratio: float = 0.5):
        self._buffer_ratio = buffer_ratio

        # Viewport state
        self._viewport_bounds: Tuple[float, float, float, float] = (0, 0, 0, 0)
        self._visible_devices: FrozenSet[str] = frozenset()
        self._buffered_devices: FrozenSet[str] = frozenset()

        # Device positions (injected from canvas)
        self._device_positions: Dict[str, Tuple[float, float, float, float]] = {}

        # Callbacks
        self._on_visibility_changed: Optional[Callable[[FrozenSet[str], FrozenSet[str]], None]] = None

    def set_visibility_callback(
        self,
        callback: Callable[[FrozenSet[str], FrozenSet[str]], None],
    ) -> None:
        """Set callback for visibility changes (visible, buffered)."""
        self._on_visibility_changed = callback

    def set_device_positions(
        self,
        positions: Dict[str, Tuple[float, float, float, float]],
    ) -> None:
        """
        Set device bounding boxes.

        Args:
            positions: Dict of device_id -> (x, y, width, height)
        """
        self._device_positions = positions

    def update_viewport(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> bool:
        """
        Update viewport bounds and recalculate visibility.

        Returns:
            True if visibility changed
        """
        new_bounds = (x, y, width, height)

        if new_bounds == self._viewport_bounds:
            return False

        self._viewport_bounds = new_bounds

        # Calculate buffer zone
        buffer_x = width * self._buffer_ratio
        buffer_y = height * self._buffer_ratio

        buffered_bounds = (
            x - buffer_x,
            y - buffer_y,
            width + 2 * buffer_x,
            height + 2 * buffer_y,
        )

        # Find visible and buffered devices
        visible: Set[str] = set()
        buffered: Set[str] = set()

        for device_id, (dx, dy, dw, dh) in self._device_positions.items():
            # Check if in viewport
            if self._intersects(
                (dx, dy, dw, dh),
                (x, y, width, height),
            ):
                visible.add(device_id)
                buffered.add(device_id)
            # Check if in buffer zone
            elif self._intersects((dx, dy, dw, dh), buffered_bounds):
                buffered.add(device_id)

        new_visible = frozenset(visible)
        new_buffered = frozenset(buffered)

        changed = new_visible != self._visible_devices or new_buffered != self._buffered_devices

        if changed:
            self._visible_devices = new_visible
            self._buffered_devices = new_buffered

            if self._on_visibility_changed:
                self._on_visibility_changed(new_visible, new_buffered)

            logger.debug(f"[ViewportManager] Visibility changed: " f"visible={len(new_visible)}, buffered={len(new_buffered)}")

        return changed

    @staticmethod
    def _intersects(
        rect1: Tuple[float, float, float, float],
        rect2: Tuple[float, float, float, float],
    ) -> bool:
        """Check if two rectangles intersect."""
        x1, y1, w1, h1 = rect1
        x2, y2, w2, h2 = rect2

        return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)

    @property
    def visible_devices(self) -> FrozenSet[str]:
        """Get currently visible devices."""
        return self._visible_devices

    @property
    def buffered_devices(self) -> FrozenSet[str]:
        """Get devices in buffer zone (includes visible)."""
        return self._buffered_devices

    def get_priority_map(self, all_devices: List[str]) -> Dict[LoadPriority, List[str]]:
        """
        Get devices organized by load priority.

        Args:
            all_devices: All device IDs on current page

        Returns:
            Dict mapping priority to device lists
        """
        priority_map: Dict[LoadPriority, List[str]] = {priority: [] for priority in LoadPriority}

        visible_set = set(self._visible_devices)
        buffered_set = set(self._buffered_devices)

        for device_id in all_devices:
            if device_id in visible_set:
                priority_map[LoadPriority.CRITICAL].append(device_id)
            elif device_id in buffered_set:
                priority_map[LoadPriority.HIGH].append(device_id)
            else:
                priority_map[LoadPriority.NORMAL].append(device_id)

        return priority_map

    def get_stats(self) -> Dict[str, Any]:
        """Get viewport statistics."""
        return {
            "viewport_bounds": self._viewport_bounds,
            "visible_count": len(self._visible_devices),
            "buffered_count": len(self._buffered_devices),
            "total_devices": len(self._device_positions),
        }


# ============================================================================
# Refresh Subscriber
# ============================================================================


@dataclass(slots=True)
class RefreshSubscriber:
    """
    Memory-efficient refresh subscriber using __slots__.
    """

    callback_ref: ref
    priority: int
    custom_interval_ms: Optional[int]
    last_refresh: float

    @classmethod
    def create(
        cls,
        callback: Callable[[], None],
        priority: int = 0,
        custom_interval_ms: Optional[int] = None,
    ) -> "RefreshSubscriber":
        """Factory method to create subscriber."""
        return cls(
            callback_ref=ref(callback),
            priority=priority,
            custom_interval_ms=custom_interval_ms,
            last_refresh=0.0,
        )

    def is_alive(self) -> bool:
        """Check if callback still exists."""
        return self.callback_ref() is not None

    def should_refresh(self, current_time: float, base_interval_ms: int) -> bool:
        """Check if subscriber should refresh now."""
        interval_ms = self.custom_interval_ms or base_interval_ms
        elapsed_ms = (current_time - self.last_refresh) * 1000
        return elapsed_ms >= interval_ms

    def refresh(self, current_time: float) -> bool:
        """Execute callback if alive."""
        callback = self.callback_ref()
        if callback is None:
            return False

        try:
            callback()
            self.last_refresh = current_time
            return True
        except Exception as e:
            logger.error(f"[RefreshSubscriber] Callback error: {e}")
            return False


# ============================================================================
# Enhanced Refresh Manager
# ============================================================================


class RefreshManager(QObject):
    """
    Advanced refresh manager with virtualization support.

    Features:
    - Subscriber-based refresh with priorities
    - Viewport-aware refresh (visible devices first)
    - Adaptive intervals based on activity
    - Pause/resume on focus changes
    - Memory-efficient weak references
    """

    refresh_executed = Signal(int)  # Number of callbacks executed
    visibility_refresh = Signal(list, list)  # visible_ids, buffered_ids

    def __init__(
        self,
        config: UIContainerConfig,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        self._config = config
        self._current_interval_ms = config.auto_refresh_interval_ms

        # Subscribers
        self._subscribers: List[RefreshSubscriber] = []

        # State
        self._is_paused = False
        self._is_idle = False
        self._is_background = False
        self._last_activity_time = time.time()

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        # Idle detection timer
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(5000)  # Check every 5s
        self._idle_timer.timeout.connect(self._check_idle)

        # Viewport manager
        self._viewport: Optional[ViewportManager] = None
        if config.enable_virtualization:
            self._viewport = ViewportManager(config.viewport_buffer_ratio)

        # Stats
        self._tick_count = 0
        self._total_refreshes = 0

        logger.debug(
            f"[RefreshManager] Initialized: "
            f"interval={config.auto_refresh_interval_ms}ms, "
            f"adaptive={config.adaptive_refresh}, "
            f"virtualization={config.enable_virtualization}"
        )

    @property
    def viewport_manager(self) -> Optional[ViewportManager]:
        """Get viewport manager for external configuration."""
        return self._viewport

    def register(
        self,
        callback: Callable[[], None],
        priority: int = 0,
        custom_interval_ms: Optional[int] = None,
    ) -> None:
        """Register a refresh callback."""
        # Check for duplicates
        for sub in self._subscribers:
            if sub.callback_ref() is callback:
                logger.debug("[RefreshManager] Callback already registered")
                return

        subscriber = RefreshSubscriber.create(
            callback=callback,
            priority=priority,
            custom_interval_ms=custom_interval_ms,
        )
        self._subscribers.append(subscriber)
        self._subscribers.sort(key=lambda s: s.priority, reverse=True)

        logger.debug(f"[RefreshManager] Registered callback: " f"priority={priority}, total={len(self._subscribers)}")

        if not self._timer.isActive() and not self._is_paused:
            self.start()

    def unregister(self, callback: Callable[[], None]) -> bool:
        """Unregister a callback."""
        initial_count = len(self._subscribers)

        self._subscribers = [sub for sub in self._subscribers if sub.callback_ref() != callback]

        removed = initial_count - len(self._subscribers)

        if removed > 0:
            logger.debug(f"[RefreshManager] Unregistered {removed} callback(s)")

        if not self._subscribers and self._timer.isActive():
            self.stop()

        return removed > 0

    def start(self) -> None:
        """Start refresh timer."""
        if self._timer.isActive():
            return

        self._is_paused = False
        self._timer.start(self._current_interval_ms)
        self._idle_timer.start()

        logger.info(f"[RefreshManager] Started: interval={self._current_interval_ms}ms")

    def stop(self) -> None:
        """Stop refresh timer."""
        if not self._timer.isActive():
            return

        self._timer.stop()
        self._idle_timer.stop()
        logger.info("[RefreshManager] Stopped")

    def pause(self) -> None:
        """Pause refresh (preserves state)."""
        if self._is_paused:
            return

        self._is_paused = True
        self._timer.stop()
        logger.debug("[RefreshManager] Paused")

    def resume(self) -> None:
        """Resume after pause."""
        if not self._is_paused:
            return

        self._is_paused = False
        self._last_activity_time = time.time()

        if self._subscribers:
            self._timer.start(self._current_interval_ms)
            logger.debug("[RefreshManager] Resumed")

    def record_activity(self) -> None:
        """Record user activity (resets idle timer)."""
        self._last_activity_time = time.time()

        if self._is_idle:
            self._is_idle = False
            self._update_interval()

    def set_background(self, is_background: bool) -> None:
        """Set background/foreground state."""
        if is_background == self._is_background:
            return

        self._is_background = is_background
        self._update_interval()

        logger.debug(f"[RefreshManager] Background mode: {is_background}")

    def _update_interval(self) -> None:
        """Update refresh interval based on state."""
        if not self._config.adaptive_refresh:
            return

        if self._is_background:
            new_interval = self._config.refresh_interval_background_ms
        elif self._is_idle:
            new_interval = self._config.refresh_interval_idle_ms
        else:
            new_interval = self._config.refresh_interval_active_ms

        if new_interval != self._current_interval_ms:
            self._current_interval_ms = new_interval

            if self._timer.isActive():
                self._timer.setInterval(new_interval)

            logger.debug(f"[RefreshManager] Interval updated: {new_interval}ms " f"(idle={self._is_idle}, bg={self._is_background})")

    def _check_idle(self) -> None:
        """Check if user is idle."""
        if self._is_paused or self._is_background:
            return

        elapsed = (time.time() - self._last_activity_time) * 1000

        if elapsed >= self._config.idle_timeout_ms and not self._is_idle:
            self._is_idle = True
            self._update_interval()
            logger.debug("[RefreshManager] User idle detected")

    def _on_tick(self) -> None:
        """Timer tick handler."""
        if self._is_paused:
            return

        self._tick_count += 1

        # Cleanup dead subscribers periodically
        if self._tick_count % CLEANUP_INTERVAL_TICKS == 0:
            self._cleanup_dead_subscribers()

        # Execute refresh
        current_time = time.time()
        executed = 0

        for subscriber in self._subscribers:
            if not subscriber.is_alive():
                continue

            if subscriber.should_refresh(current_time, self._current_interval_ms):
                if subscriber.refresh(current_time):
                    executed += 1

        if executed > 0:
            self._total_refreshes += executed
            self.refresh_executed.emit(executed)

        # Emit visibility-aware refresh signal
        if self._viewport:
            visible = list(self._viewport.visible_devices)
            buffered = list(self._viewport.buffered_devices - self._viewport.visible_devices)
            self.visibility_refresh.emit(visible, buffered)

    def _cleanup_dead_subscribers(self) -> None:
        """Remove dead weak references."""
        before = len(self._subscribers)
        self._subscribers = [s for s in self._subscribers if s.is_alive()]
        after = len(self._subscribers)

        if before > after:
            logger.debug(f"[RefreshManager] Cleaned up {before - after} dead subscriber(s)")

            if after == 0 and self._timer.isActive():
                self.stop()

    def get_stats(self) -> Dict[str, Any]:
        """Get refresh statistics."""
        alive_count = sum(1 for s in self._subscribers if s.is_alive())

        stats = {
            "tick_count": self._tick_count,
            "total_refreshes": self._total_refreshes,
            "active_subscribers": alive_count,
            "total_subscribers": len(self._subscribers),
            "current_interval_ms": self._current_interval_ms,
            "is_paused": self._is_paused,
            "is_idle": self._is_idle,
            "is_background": self._is_background,
            "is_running": self._timer.isActive(),
        }

        if self._viewport:
            stats["viewport"] = self._viewport.get_stats()

        return stats

    def shutdown(self) -> None:
        """Cleanup resources."""
        self.stop()
        self._subscribers.clear()
        logger.info("[RefreshManager] Shutdown complete")


# ============================================================================
# Service Registry
# ============================================================================


class ServiceRegistry:
    """
    Thread-safe service registry with lazy initialization.
    """

    def __init__(self):
        self._factories: Dict[type, Callable] = {}
        self._instances: WeakValueDictionary = WeakValueDictionary()

    def register(self, service_type: type, factory: Callable[[], T]) -> None:
        """Register a service factory."""
        self._factories[service_type] = factory

    def get(self, service_type: type) -> T:
        """Get or create service instance."""
        instance = self._instances.get(service_type)

        if instance is None:
            if service_type not in self._factories:
                raise KeyError(f"Service {service_type} not registered")
            instance = self._factories[service_type]()
            self._instances[service_type] = instance

        return instance

    def has(self, service_type: type) -> bool:
        """Check if service is registered."""
        return service_type in self._factories

    def clear(self) -> None:
        """Clear all instances."""
        self._instances.clear()


# ============================================================================
# Sub-Containers
# ============================================================================


class ServicesContainer:
    """Container for core services."""

    def __init__(self, app_container: "AppContainer"):
        self._app = app_container
        self._theme_service: Optional["ThemeService"] = None
        self._icon_service: Optional["IconService"] = None
        self._page_manager: Optional["PageDeviceManager"] = None
        self._id_mapper: Optional["DeviceFileAdapter"] = None

    @property
    def theme_service(self) -> "ThemeService":
        if self._theme_service is None:
            from ..services.theme_service import get_theme_service

            self._theme_service = get_theme_service()
            logger.debug("[Services] ThemeService initialized")
        return self._theme_service

    @property
    def icon_service(self) -> "IconService":
        if self._icon_service is None:
            from ..services.icon_service import get_icon_service

            self._icon_service = get_icon_service(self.theme_service)
            logger.debug("[Services] IconService initialized")
        return self._icon_service

    @property
    def page_manager(self) -> "PageDeviceManager":
        if self._page_manager is None:
            from ..services.page_device_manager import PageDeviceManager

            config_path = self._get_config_path()
            self._page_manager = PageDeviceManager(config_path=config_path)
            logger.debug("[Services] PageDeviceManager initialized")
        return self._page_manager

    @property
    def id_mapper(self) -> Optional["DeviceFileAdapter"]:
        if self._id_mapper is None:
            self._id_mapper = self._init_id_mapper()
        return self._id_mapper

    def _get_config_path(self) -> Optional[str]:
        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            return PATHS.device_positions_path
        except ImportError:
            return None

    def _init_id_mapper(self) -> Optional["DeviceFileAdapter"]:
        """Initialize ID mapper."""
        try:
            for attr in ("device_file_adapter", "id_mapper"):
                mapper = getattr(self._app, attr, None)
                if mapper:
                    logger.debug(f"[Services] Using ID mapper from AppContainer.{attr}")
                    return mapper

            from iFactory.infrastructure.adapters.device_file_adapter import (
                DeviceFileAdapter,
            )

            mapper = DeviceFileAdapter()
            logger.debug("[Services] Created local DeviceFileAdapter")
            return mapper

        except Exception as e:
            logger.warning(f"[Services] Failed to init ID mapper: {e}")
            return None

    def preload_icons(self) -> int:
        """Preload commonly used icons."""
        count = self.icon_service.preload_navigation_icons()
        count += self.icon_service.preload_action_icons()

        try:
            all_devices = self.page_manager.get_all_devices()
            device_codes = set()

            for device_id in all_devices:
                if len(device_id) >= 3:
                    if device_id.startswith(("CA1", "CA2")):
                        device_codes.add(device_id[:3])
                    else:
                        base = "".join(c for c in device_id[:3] if c.isalpha())
                        if base:
                            device_codes.add(base.upper())

            count += self.icon_service.preload_device_icons(list(device_codes))
        except Exception as e:
            logger.warning(f"[Services] Device icon preload failed: {e}")

        return count

    def shutdown(self) -> None:
        """Cleanup services."""
        if self._icon_service:
            self._icon_service.clear_cache()


class StateContainer:
    """Container for state management."""

    def __init__(self, config: UIContainerConfig):
        self._config = config
        self._store: Optional["Store"] = None

    @property
    def store(self) -> "Store":
        if self._store is None:
            self._store = self._create_store()
        return self._store

    def _create_store(self) -> "Store":
        from ..state.store import Store, StoreConfig, LocalStoragePersistence
        from ..state.reducers import INITIAL_STATE_DICT
        from pathlib import Path

        persistence = None
        if self._config.persist_state and self._config.state_persistence_path:
            persistence = LocalStoragePersistence(Path(self._config.state_persistence_path))

        store_config = StoreConfig(
            enable_time_travel=self._config.enable_time_travel,
            persistence=persistence,
            enable_logging=True,
        )

        return Store(
            initial_state=INITIAL_STATE_DICT,
            config=store_config,
        )

    def shutdown(self) -> None:
        """Cleanup state."""
        pass


class ViewModelsContainer:
    """Container for ViewModels."""

    def __init__(
        self,
        app_container: "AppContainer",
        services: ServicesContainer,
    ):
        self._app = app_container
        self._services = services

        self._shell_vm: Optional["ShellViewModel"] = None
        self._device_vm: Optional["DeviceListViewModel"] = None
        self._gantt_vm: Optional["GanttChartViewModel"] = None
        self._sync_orchestrator: Optional["SyncOrchestrator"] = None
        self._dependencies_wired: bool = False

    @property
    def sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        if self._sync_orchestrator is None:
            self._sync_orchestrator = self._init_sync_orchestrator()
        return self._sync_orchestrator

    @property
    def shell_vm(self) -> "ShellViewModel":
        if self._shell_vm is None:
            self._shell_vm = self._create_shell_vm()
            self._try_wire_dependencies()
        return self._shell_vm

    @property
    def device_vm(self) -> "DeviceListViewModel":
        if self._device_vm is None:
            self._device_vm = self._create_device_vm()
            self._try_wire_dependencies()
        return self._device_vm

    @property
    def gantt_vm(self) -> "GanttChartViewModel":
        if self._gantt_vm is None:
            self._gantt_vm = self._create_gantt_vm()
        return self._gantt_vm

    def _init_sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        """Get or create SyncOrchestrator."""
        try:
            if hasattr(self._app, "sync_orchestrator") and self._app.sync_orchestrator:
                logger.debug("[ViewModels] Using SyncOrchestrator from AppContainer")
                return self._app.sync_orchestrator

            remote_source = getattr(self._app, "remote_source", None)
            if remote_source:
                from iFactory.application.services.sync_orchestrator import (
                    create_sync_orchestrator,
                )

                orchestrator = create_sync_orchestrator(
                    remote_source=remote_source,
                    uow_factory=getattr(self._app, "uow_factory", None) or self._null_uow_factory(),
                    id_mapper=self._services.id_mapper,
                )
                logger.debug("[ViewModels] Created local SyncOrchestrator")
                return orchestrator

            logger.warning("[ViewModels] No remote source - SyncOrchestrator disabled")
            return None

        except Exception as e:
            logger.error(f"[ViewModels] SyncOrchestrator init failed: {e}")
            return None

    def _null_uow_factory(self):
        """Create no-op UoW factory."""
        from iFactory.application.ports.uow import AbstractUnitOfWork

        class NullUoW(AbstractUnitOfWork):
            devices = None
            history = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def commit(self):
                pass

            async def rollback(self):
                pass

        return lambda: NullUoW()

    def _create_shell_vm(self) -> "ShellViewModel":
        from ..viewmodels import ShellViewModel

        vm = ShellViewModel(
            theme_service=self._services.theme_service,
            config_path=self._services._get_config_path(),
            page_manager=self._services.page_manager,
        )
        vm.initialize()
        return vm

    def _create_device_vm(self) -> "DeviceListViewModel":
        from ..viewmodels import DeviceListViewModel

        remote_source = getattr(self._app, "remote_source", None)

        vm = DeviceListViewModel(
            page_manager=self._services.page_manager,
            remote_source=remote_source,
            sync_orchestrator=self.sync_orchestrator,
            shell_vm=self._shell_vm,
            id_mapper=self._services.id_mapper,
        )
        vm.initialize()
        return vm

    def _create_gantt_vm(self) -> "GanttChartViewModel":
        from ..viewmodels import GanttChartViewModel

        mssql_url = None
        if hasattr(self._app, "db_config") and self._app.db_config:
            mssql_url = self._app.db_config.mssql_url

        vm = GanttChartViewModel(
            mssql_url=mssql_url,
            id_mapper=self._services.id_mapper,
        )
        vm.initialize()
        return vm

    def _try_wire_dependencies(self) -> None:
        """Auto-wire VM dependencies."""
        if self._dependencies_wired:
            return

        if self._device_vm is not None and self._shell_vm is not None:
            if self._device_vm._shell_vm is None:
                self._device_vm.set_shell_viewmodel(self._shell_vm)
                logger.debug("[ViewModels] Auto-wired DeviceVM -> ShellVM")
            self._dependencies_wired = True

    def wire_dependencies(self) -> None:
        """Explicit dependency wiring."""
        if self._dependencies_wired:
            return

        _ = self.shell_vm
        _ = self.device_vm

        if self._device_vm and self._shell_vm:
            if self._device_vm._shell_vm is None:
                self._device_vm.set_shell_viewmodel(self._shell_vm)
                logger.debug("[ViewModels] Explicitly wired DeviceVM -> ShellVM")
            self._dependencies_wired = True

    def shutdown(self) -> None:
        """Cleanup ViewModels."""
        for vm in (self._device_vm, self._gantt_vm, self._shell_vm):
            if vm and hasattr(vm, "dispose"):
                vm.dispose()


# ============================================================================
# Main UIContainer
# ============================================================================


class UIContainer(QObject):
    """
    Enhanced UI Container with advanced optimizations.

    Features:
    - Progressive loading with priority queue
    - Predictive prefetching
    - Viewport-aware refresh (virtualization)
    - Adaptive refresh intervals
    - Memory-efficient architecture
    """

    # Signals
    loading_progress = Signal(int, int)  # current, total
    prefetch_triggered = Signal(str, list)  # page_name, device_ids

    def __init__(
        self,
        app_container: "AppContainer",
        config: Optional[UIContainerConfig] = None,
    ):
        super().__init__()

        self._app = app_container
        self._config = config or UIContainerConfig()

        # State flags
        self._is_initialized = False
        self._initial_load_done = False
        self._is_shutting_down = False

        # Sub-containers
        self._services: Optional[ServicesContainer] = None
        self._state: Optional[StateContainer] = None
        self._viewmodels: Optional[ViewModelsContainer] = None

        # Main window
        self._main_window: Optional["MainWindow"] = None

        # Advanced components
        self._refresh_manager: Optional[RefreshManager] = None
        self._load_queue: Optional[ProgressiveLoadQueue] = None
        self._prefetcher: Optional[PredictivePrefetcher] = None

    # ========================================================================
    # Initialization
    # ========================================================================

    def initialize(self) -> None:
        """Initialize all UI components."""
        if self._is_initialized:
            return

        logger.info("[UIContainer] Initializing...")

        try:
            # 1. Services
            self._services = ServicesContainer(self._app)
            if self._config.preload_icons:
                count = self._services.preload_icons()
                logger.info(f"[UIContainer] Preloaded {count} icons")

            # 2. State
            self._state = StateContainer(self._config)

            # 3. ViewModels
            self._viewmodels = ViewModelsContainer(self._app, self._services)

            # 4. Main Window
            self._init_main_window()

            # 5. Wire dependencies
            self._viewmodels.wire_dependencies()

            # 6. Connect signals
            self._connect_signals()

            # 7. Initialize advanced components
            self._init_refresh_manager()
            self._init_progressive_loader()
            self._init_prefetcher()

            self._is_initialized = True
            logger.info("[UIContainer] Initialized successfully")

        except Exception as e:
            logger.error(f"[UIContainer] Initialization failed: {e}")
            raise

    def _init_main_window(self) -> None:
        """Initialize main window."""
        from ..views.main_window import MainWindow

        self._main_window = MainWindow(
            store=self._state.store,
            shell_vm=self._viewmodels.shell_vm,
            device_vm=self._viewmodels.device_vm,
            gantt_vm=self._viewmodels.gantt_vm,
            theme_service=self._services.theme_service,
            page_manager=self._services.page_manager,
        )

        if self._config.pause_on_unfocus:
            self._main_window.installEventFilter(self)

    def _connect_signals(self) -> None:
        """Connect ViewModel signals to Store."""
        store = self._state.store
        device_vm = self._viewmodels.device_vm
        shell_vm = self._viewmodels.shell_vm
        gantt_vm = self._viewmodels.gantt_vm

        # Device signals
        if device_vm:
            device_vm.devicesChanged.connect(self._on_devices_changed)
            device_vm.selectionChanged.connect(self._on_selection_changed)
            device_vm.syncStatusChanged.connect(self._on_sync_status_changed)

        # Shell signals
        if shell_vm:
            shell_vm.themeChanged.connect(self._on_theme_changed)
            shell_vm.pageChanged.connect(self._on_page_changed)
            shell_vm.sidebarChanged.connect(self._on_sidebar_changed)
            shell_vm.rightPanelChanged.connect(self._on_right_panel_changed)

        # Gantt signals
        if gantt_vm:
            gantt_vm.chartReady.connect(self._on_chart_ready)

    def _init_refresh_manager(self) -> None:
        """Initialize enhanced refresh manager."""
        self._refresh_manager = RefreshManager(self._config, parent=self)

        # Register device VM refresh
        if self._viewmodels and self._viewmodels._device_vm:
            self._refresh_manager.register(
                callback=self._on_auto_refresh,
                priority=10,
            )

        # Connect visibility-aware refresh
        self._refresh_manager.visibility_refresh.connect(self._on_visibility_refresh)

        logger.info(f"[UIContainer] RefreshManager initialized: " f"{self._config.auto_refresh_interval_ms}ms")

    def _init_progressive_loader(self) -> None:
        """Initialize progressive loading queue."""
        if not self._config.enable_progressive_loading:
            return

        self._load_queue = ProgressiveLoadQueue(
            batch_size=self._config.progressive_batch_size,
            batch_delay_ms=self._config.progressive_batch_delay_ms,
        )

        self._load_queue.set_batch_callback(self._on_load_batch_ready)

        logger.info("[UIContainer] Progressive loader initialized")

    def _init_prefetcher(self) -> None:
        """Initialize predictive prefetcher."""
        if not self._config.enable_prefetching:
            return

        self._prefetcher = PredictivePrefetcher(
            max_prefetch_items=self._config.prefetch_max_items,
            prefetch_delay_ms=self._config.prefetch_delay_ms,
        )

        self._prefetcher.set_prefetch_callback(self._on_prefetch_triggered)

        # Populate page devices - FIXED: Safe method checking
        if self._services and self._services._page_manager:
            try:
                page_manager = self._services.page_manager

                # Use get_all_page_devices if available
                if hasattr(page_manager, "get_all_page_devices"):
                    page_devices = page_manager.get_all_page_devices()
                    self._prefetcher.set_page_devices(page_devices)
                    logger.debug(f"[UIContainer] Set {len(page_devices)} page device mappings")
                else:
                    # Fallback: build from other methods
                    logger.debug("[UIContainer] Building page devices from individual methods")
                    page_devices = {}

                    if hasattr(page_manager, "get_all_page_names"):
                        for page_name in page_manager.get_all_page_names():
                            devices = page_manager.get_page_devices(page_name)
                            if devices:
                                page_devices[page_name] = devices

                    if page_devices:
                        self._prefetcher.set_page_devices(page_devices)
                        logger.debug(f"[UIContainer] Built {len(page_devices)} page mappings")

            except Exception as e:
                logger.warning(f"[UIContainer] Failed to set page devices: {e}")

        logger.info("[UIContainer] Prefetcher initialized")

    # ========================================================================
    # Signal Handlers
    # ========================================================================

    def _on_devices_changed(self, devices: dict) -> None:
        from ..state.actions import load_devices

        self._state.store.dispatch(load_devices(devices))

    def _on_selection_changed(self, selection) -> None:
        from ..state.actions import select_device_only, deselect_device

        if selection.has_selection:
            self._state.store.dispatch(select_device_only(selection.selected_device_id))

            # Promote selected device to critical priority
            if self._load_queue:
                self._load_queue.promote(selection.selected_device_id, LoadPriority.CRITICAL)
        else:
            self._state.store.dispatch(deselect_device())

    def _on_sync_status_changed(self, status) -> None:
        from ..state.actions import update_system_status, set_loading

        self._state.store.dispatch(set_loading(status.is_syncing))

        if status.has_error:
            self._state.store.dispatch(update_system_status(mssql=False, sqlite=True, message=status.error_message))
        elif status.last_sync_time:
            self._state.store.dispatch(
                update_system_status(
                    mssql=True,
                    sqlite=True,
                    message=f"Synced {status.synced_count} devices @ {status.last_sync_time}",
                )
            )

    def _on_theme_changed(self, theme: str) -> None:
        from ..state.actions import set_theme

        self._state.store.dispatch(set_theme(theme))

    def _on_page_changed(self, page: str) -> None:
        from ..state.actions import set_page

        self._state.store.dispatch(set_page(page))

        # Record navigation for prefetching
        if self._prefetcher:
            self._prefetcher.record_navigation(page)

        # Clear prefetch cache on page change
        if self._prefetcher:
            self._prefetcher.clear_cache()

    def _on_sidebar_changed(self, expanded: bool) -> None:
        state = self._state.store.get_state()
        if state.get("sidebar_expanded") != expanded:
            from ..state.actions import toggle_sidebar

            self._state.store.dispatch(toggle_sidebar())

    def _on_right_panel_changed(self, expanded: bool) -> None:
        state = self._state.store.get_state()
        if state.get("right_panel_expanded") != expanded:
            from ..state.actions import toggle_right_panel

            self._state.store.dispatch(toggle_right_panel())

    def _on_chart_ready(self, chart) -> None:
        from ..state.actions import set_selected_device_gantt

        self._state.store.dispatch(set_selected_device_gantt(chart))

    def _on_auto_refresh(self) -> None:
        """Handle auto-refresh tick."""
        if self._is_shutting_down:
            return

        if self._viewmodels and self._viewmodels._device_vm:
            # Use viewport-aware refresh if available
            viewport = self._refresh_manager.viewport_manager if self._refresh_manager else None

            if viewport and viewport.visible_devices:
                # Refresh visible devices first, then others
                visible = list(viewport.visible_devices)
                self._viewmodels.device_vm.load_devices(visible)
            else:
                # Full refresh
                self._viewmodels.device_vm.load_devices()

    def _on_visibility_refresh(self, visible_ids: List[str], buffered_ids: List[str]) -> None:
        """Handle visibility-aware refresh signal."""
        if not self._viewmodels or not self._viewmodels._device_vm:
            return

        # Progressive load: visible first, then buffered
        if self._load_queue:
            priority_map = {
                LoadPriority.CRITICAL: visible_ids,
                LoadPriority.HIGH: buffered_ids,
            }
            self._load_queue.enqueue_with_priority_map(priority_map)

    def _on_load_batch_ready(self, device_ids: List[str], priority: LoadPriority) -> None:
        """Handle progressive load batch."""
        if not self._viewmodels or not self._viewmodels._device_vm:
            return

        logger.debug(f"[UIContainer] Loading batch: " f"{len(device_ids)} devices at {priority.name}")

        self._viewmodels.device_vm.load_devices(device_ids)
        self.loading_progress.emit(len(device_ids), len(device_ids))

    def _on_prefetch_triggered(self, page_name: str, device_ids: List[str]) -> None:
        """Handle prefetch trigger."""
        if not self._viewmodels or not self._viewmodels._device_vm:
            return

        logger.debug(f"[UIContainer] Prefetching: " f"{len(device_ids)} devices for page {page_name}")

        # Use low priority for prefetch
        if self._load_queue:
            self._load_queue.enqueue(device_ids, LoadPriority.LOW)
        else:
            self._viewmodels.device_vm.load_devices(device_ids)

        self.prefetch_triggered.emit(page_name, device_ids)

    # ========================================================================
    # Event Filter
    # ========================================================================

    def eventFilter(self, obj, event) -> bool:
        """Handle window focus events."""
        if obj == self._main_window and self._config.pause_on_unfocus:
            from PySide6.QtCore import QEvent

            if event.type() == QEvent.Type.WindowDeactivate:
                self.pause_auto_refresh()
                if self._refresh_manager:
                    self._refresh_manager.set_background(True)
                logger.debug("[UIContainer] Window unfocused")

            elif event.type() == QEvent.Type.WindowActivate:
                self.resume_auto_refresh()
                if self._refresh_manager:
                    self._refresh_manager.set_background(False)
                logger.debug("[UIContainer] Window focused")

        return super().eventFilter(obj, event)

    # ========================================================================
    # Public API - Auto Refresh
    # ========================================================================

    def start_auto_refresh(self) -> None:
        """Start auto-refresh."""
        if self._refresh_manager:
            self._refresh_manager.start()

    def stop_auto_refresh(self) -> None:
        """Stop auto-refresh."""
        if self._refresh_manager:
            self._refresh_manager.stop()

    def pause_auto_refresh(self) -> None:
        """Pause auto-refresh."""
        if self._refresh_manager:
            self._refresh_manager.pause()

    def resume_auto_refresh(self) -> None:
        """Resume auto-refresh."""
        if self._refresh_manager:
            self._refresh_manager.resume()

    def record_user_activity(self) -> None:
        """Record user activity (resets idle timer)."""
        if self._refresh_manager:
            self._refresh_manager.record_activity()

    def register_refresh_callback(
        self,
        callback: Callable[[], None],
        priority: int = 0,
        custom_interval_ms: Optional[int] = None,
    ) -> None:
        """Register a custom refresh callback."""
        if self._refresh_manager:
            self._refresh_manager.register(
                callback=callback,
                priority=priority,
                custom_interval_ms=custom_interval_ms,
            )

    def unregister_refresh_callback(self, callback: Callable[[], None]) -> bool:
        """Unregister a refresh callback."""
        if self._refresh_manager:
            return self._refresh_manager.unregister(callback)
        return False

    # ========================================================================
    # Public API - Progressive Loading
    # ========================================================================

    def load_devices_progressive(
        self,
        device_ids: List[str],
        priority: LoadPriority = LoadPriority.NORMAL,
    ) -> None:
        """
        Load devices using progressive queue.

        Args:
            device_ids: Devices to load
            priority: Loading priority
        """
        if self._load_queue:
            self._load_queue.enqueue(device_ids, priority)
        elif self._viewmodels and self._viewmodels._device_vm:
            self._viewmodels.device_vm.load_devices(device_ids)

    def load_with_viewport_priority(
        self,
        all_devices: List[str],
    ) -> None:
        """
        Load devices with viewport-aware priority.

        Visible devices are loaded first, then buffered, then rest.
        """
        if not self._refresh_manager or not self._refresh_manager.viewport_manager:
            # Fallback to normal load
            self.load_devices_progressive(all_devices)
            return

        viewport = self._refresh_manager.viewport_manager
        priority_map = viewport.get_priority_map(all_devices)

        if self._load_queue:
            self._load_queue.enqueue_with_priority_map(priority_map)
        else:
            # Load in priority order
            for priority in LoadPriority:
                devices = priority_map.get(priority, [])
                if devices and self._viewmodels and self._viewmodels._device_vm:
                    self._viewmodels.device_vm.load_devices(devices)

    # ========================================================================
    # Public API - Viewport
    # ========================================================================

    def update_viewport(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """Update viewport bounds for virtualization."""
        if self._refresh_manager and self._refresh_manager.viewport_manager:
            self._refresh_manager.viewport_manager.update_viewport(x, y, width, height)

    def set_device_positions(
        self,
        positions: Dict[str, Tuple[float, float, float, float]],
    ) -> None:
        """Set device positions for viewport calculations."""
        if self._refresh_manager and self._refresh_manager.viewport_manager:
            self._refresh_manager.viewport_manager.set_device_positions(positions)

    # ========================================================================
    # Public API - Prefetching
    # ========================================================================

    def prefetch_page(self, page_name: str) -> None:
        """Manually trigger prefetch for a page."""
        if not self._prefetcher or not self._services:
            return

        try:
            devices = self._services.page_manager.get_page_devices(page_name)
            if devices:
                self._on_prefetch_triggered(page_name, devices[: self._config.prefetch_max_items])
        except Exception as e:
            logger.warning(f"[UIContainer] Prefetch failed for {page_name}: {e}")

    def on_page_hover(self, page_name: str) -> None:
        """Handle hover over page link (triggers delayed prefetch)."""
        if self._prefetcher:
            self._prefetcher.on_hover_page(page_name)

    # ========================================================================
    # Data Loading
    # ========================================================================

    def schedule_deferred_data_load(self) -> None:
        """Schedule deferred data loading after window shown."""
        QTimer.singleShot(
            self._config.deferred_load_delay_ms,
            self._start_data_loading,
        )

    def _start_data_loading(self) -> None:
        """Start initial data loading with progressive approach."""
        if self._initial_load_done:
            return

        self._initial_load_done = True
        logger.info("[UIContainer] Starting initial data load...")

        # Get current page devices - FIXED: Load full page data
        if self._services and self._services._page_manager:
            try:
                page_manager = self._services.page_manager

                # Get current page
                if hasattr(page_manager, "current_page"):
                    current_page = page_manager.current_page
                elif hasattr(page_manager, "get_current_page"):
                    current_page = page_manager.get_current_page()
                else:
                    current_page = "electrode_page"

                # ✅ FIX: Force load current page first
                page_manager.force_load_current_page()

                # Then optionally load with viewport priority
                devices = page_manager.get_page_devices(current_page)
                if devices and self._load_queue and self._config.enable_progressive_loading:
                    logger.debug(f"[UIContainer] Progressive loading {len(devices)} devices for {current_page}")
                    self.load_with_viewport_priority(devices)

            except Exception as e:
                logger.warning(f"[UIContainer] Initial load error: {e}")
                # Fallback: force load current page
                if self._services._page_manager:
                    try:
                        self._services.page_manager.force_load_current_page()
                    except Exception as fallback_error:
                        logger.error(f"[UIContainer] Fallback load also failed: {fallback_error}")

        # Start auto-refresh
        self.start_auto_refresh()
        logger.info("[UIContainer] Auto-refresh started")

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = {
            "initialized": self._is_initialized,
            "initial_load_done": self._initial_load_done,
        }

        if self._refresh_manager:
            stats["refresh"] = self._refresh_manager.get_stats()

        if self._load_queue:
            stats["progressive_loader"] = self._load_queue.get_stats()

        if self._prefetcher:
            stats["prefetcher"] = self._prefetcher.get_stats()

        return stats

    # ========================================================================
    # Getters
    # ========================================================================

    def get_main_window(self) -> Optional["MainWindow"]:
        return self._main_window

    def get_device_viewmodel(self) -> Optional["DeviceListViewModel"]:
        return self._viewmodels.device_vm if self._viewmodels else None

    def get_gantt_viewmodel(self) -> Optional["GanttChartViewModel"]:
        return self._viewmodels.gantt_vm if self._viewmodels else None

    def get_shell_viewmodel(self) -> Optional["ShellViewModel"]:
        return self._viewmodels.shell_vm if self._viewmodels else None

    def get_page_manager(self) -> Optional["PageDeviceManager"]:
        return self._services.page_manager if self._services else None

    def get_store(self) -> Optional["Store"]:
        return self._state.store if self._state else None

    def get_theme_service(self) -> Optional["ThemeService"]:
        return self._services.theme_service if self._services else None

    def get_icon_service(self) -> Optional["IconService"]:
        return self._services.icon_service if self._services else None

    def get_id_mapper(self) -> Optional["DeviceFileAdapter"]:
        return self._services.id_mapper if self._services else None

    def get_refresh_manager(self) -> Optional[RefreshManager]:
        return self._refresh_manager

    def get_load_queue(self) -> Optional[ProgressiveLoadQueue]:
        return self._load_queue

    def get_prefetcher(self) -> Optional[PredictivePrefetcher]:
        return self._prefetcher

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def shutdown(self) -> None:
        """Shutdown all components."""
        if not self._is_initialized:
            return

        self._is_shutting_down = True
        logger.info("[UIContainer] Shutting down...")

        # Stop refresh manager
        if self._refresh_manager:
            self._refresh_manager.shutdown()
            self._refresh_manager = None

        # Clear load queue
        if self._load_queue:
            self._load_queue.clear()
            self._load_queue = None

        # Clear prefetcher
        if self._prefetcher:
            self._prefetcher.clear_cache()
            self._prefetcher = None

        # Shutdown sub-containers
        if self._viewmodels:
            self._viewmodels.shutdown()

        if self._services:
            self._services.shutdown()

        if self._state:
            self._state.shutdown()

        # Close window
        if self._main_window:
            self._main_window.close()

        self._is_initialized = False
        logger.info("[UIContainer] Shutdown complete")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Main container
    "UIContainer",
    "UIContainerConfig",
    # Sub-containers
    "ServicesContainer",
    "StateContainer",
    "ViewModelsContainer",
    # Optimization components
    "RefreshManager",
    "ProgressiveLoadQueue",
    "PredictivePrefetcher",
    "ViewportManager",
    # Supporting types
    "LoadPriority",
    "LoadRequest",
    "RefreshSubscriber",
    "ServiceRegistry",
]
