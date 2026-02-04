# src/iFactory/presentation/adapters/signal_bus.py
"""
Enhanced Signal Bus with priority and filtering.

Features:
- Throttling for high-frequency signals
- Priority-based emission
- Topic filtering
- Weak references
"""

from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class SignalPriority(IntEnum):
    """Signal emission priority."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class SignalEvent:
    """Event data for signal emission."""

    topic: str
    data: Any
    priority: SignalPriority = SignalPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None


class SignalThrottler(QObject):
    """
    Throttles high-frequency signal emissions.

    Batches updates and emits at most once per interval.
    Supports priority override for critical updates.
    """

    flushed = Signal(object)

    def __init__(
        self,
        interval_ms: int = 50,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._pending_data: Optional[Any] = None
        self._pending_priority: SignalPriority = SignalPriority.NORMAL
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)
        self._emit_count = 0
        self._drop_count = 0

    def push(
        self,
        data: Any,
        priority: SignalPriority = SignalPriority.NORMAL,
    ) -> None:
        """Push data to be emitted (batched)."""
        # Higher priority overrides pending
        if self._pending_data is not None:
            if priority <= self._pending_priority:
                self._drop_count += 1
            else:
                self._pending_data = data
                self._pending_priority = priority
        else:
            self._pending_data = data
            self._pending_priority = priority

        # Critical priority flushes immediately
        if priority == SignalPriority.CRITICAL:
            self.flush_now()
            return

        if not self._timer.isActive():
            self._timer.start(self._interval_ms)

    def _flush(self) -> None:
        """Emit batched data."""
        if self._pending_data is not None:
            self.flushed.emit(self._pending_data)
            self._emit_count += 1
            self._pending_data = None
            self._pending_priority = SignalPriority.NORMAL

    def flush_now(self) -> None:
        """Force immediate flush."""
        self._timer.stop()
        self._flush()

    def cancel(self) -> None:
        """Cancel pending emission."""
        self._timer.stop()
        self._pending_data = None
        self._pending_priority = SignalPriority.NORMAL

    @property
    def stats(self) -> Dict[str, int]:
        """Get throttler statistics."""
        return {
            "emit_count": self._emit_count,
            "drop_count": self._drop_count,
        }


class TopicFilter:
    """
    Filter for topic-based subscriptions.

    Supports wildcards:
    - "devices.*" matches "devices.updated", "devices.selected"
    - "*" matches all topics
    """

    def __init__(self, pattern: str):
        self._pattern = pattern
        self._parts = pattern.split(".")

    def matches(self, topic: str) -> bool:
        """Check if topic matches filter pattern."""
        if self._pattern == "*":
            return True

        topic_parts = topic.split(".")

        for i, part in enumerate(self._parts):
            if part == "*":
                return True
            if i >= len(topic_parts):
                return False
            if part != topic_parts[i]:
                return False

        return len(topic_parts) == len(self._parts)


@dataclass
class Subscription:
    """Subscription to signal bus."""

    callback: Callable[[SignalEvent], None]
    filter: Optional[TopicFilter] = None
    priority: SignalPriority = SignalPriority.NORMAL
    weak_ref: Optional[weakref.ref] = None


class SignalBus(QObject):
    """
    Enhanced signal bus for application-wide events.

    Features:
    - Topic-based pub/sub
    - Priority handling
    - Throttling for high-frequency signals
    - Weak reference support
    - Statistics tracking

    Usage:
        bus = get_signal_bus()

        # Subscribe to topics
        bus.subscribe("devices.updated", handler)
        bus.subscribe("devices.*", handler)  # Wildcard

        # Emit events
        bus.emit("devices.updated", data)
        bus.emit("devices.updated", data, priority=SignalPriority.HIGH)
    """

    # Built-in signals for backward compatibility
    devices_updated = Signal(dict)
    gantt_updated = Signal(dict)
    error_occurred = Signal(str)
    loading_changed = Signal(bool)
    theme_changed = Signal(str)
    page_changed = Signal(str)
    device_selected = Signal(str)
    device_deselected = Signal()

    THROTTLE_INTERVAL_MS = 50

    _instance: Optional["SignalBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._initialized = True

        # Throttlers
        self._throttlers: Dict[str, SignalThrottler] = {}
        self._devices_throttler = SignalThrottler(self.THROTTLE_INTERVAL_MS, self)
        self._devices_throttler.flushed.connect(self._emit_devices_internal)
        self._gantt_throttler = SignalThrottler(self.THROTTLE_INTERVAL_MS, self)
        self._gantt_throttler.flushed.connect(self._emit_gantt_internal)

        # Topic subscriptions
        self._subscriptions: Dict[str, List[Subscription]] = {}

        # Statistics
        self._emit_count = 0
        self._topic_counts: Dict[str, int] = {}

        logger.debug("[SignalBus] Initialized with throttling")

    # ========================================================================
    # Topic-based Pub/Sub
    # ========================================================================

    def subscribe(
        self,
        topic_pattern: str,
        callback: Callable[[SignalEvent], None],
        priority: SignalPriority = SignalPriority.NORMAL,
        weak: bool = False,
    ) -> Callable[[], None]:
        """
        Subscribe to a topic.

        Args:
            topic_pattern: Topic pattern (supports wildcards)
            callback: Handler function
            priority: Subscription priority
            weak: Use weak reference for callback

        Returns:
            Unsubscribe function
        """
        topic_filter = TopicFilter(topic_pattern)

        subscription = Subscription(
            callback=callback,
            filter=topic_filter,
            priority=priority,
            weak_ref=weakref.ref(callback) if weak else None,
        )

        if topic_pattern not in self._subscriptions:
            self._subscriptions[topic_pattern] = []

        self._subscriptions[topic_pattern].append(subscription)

        def unsubscribe():
            if topic_pattern in self._subscriptions:
                try:
                    self._subscriptions[topic_pattern].remove(subscription)
                except ValueError:
                    pass

        return unsubscribe

    def emit(
        self,
        topic: str,
        data: Any,
        priority: SignalPriority = SignalPriority.NORMAL,
        source: Optional[str] = None,
        throttle: bool = False,
    ) -> None:
        """
        Emit an event.

        Args:
            topic: Event topic
            data: Event data
            priority: Emission priority
            source: Event source identifier
            throttle: Whether to throttle this emission
        """
        event = SignalEvent(
            topic=topic,
            data=data,
            priority=priority,
            source=source,
        )

        if throttle:
            throttler = self._get_throttler(topic)
            throttler.push(event, priority)
        else:
            self._dispatch_event(event)

    def _get_throttler(self, topic: str) -> SignalThrottler:
        """Get or create throttler for topic."""
        if topic not in self._throttlers:
            throttler = SignalThrottler(self.THROTTLE_INTERVAL_MS, self)
            throttler.flushed.connect(self._dispatch_event)
            self._throttlers[topic] = throttler
        return self._throttlers[topic]

    def _dispatch_event(self, event: SignalEvent) -> None:
        """Dispatch event to matching subscribers."""
        self._emit_count += 1
        self._topic_counts[event.topic] = self._topic_counts.get(event.topic, 0) + 1

        # Collect matching subscribers
        matching: List[Subscription] = []

        for pattern, subs in self._subscriptions.items():
            for sub in subs:
                if sub.filter and sub.filter.matches(event.topic):
                    matching.append(sub)

        # Sort by priority (higher first)
        matching.sort(key=lambda s: s.priority, reverse=True)

        # Dispatch
        dead_subs: List[tuple] = []

        for sub in matching:
            try:
                if sub.weak_ref:
                    callback = sub.weak_ref()
                    if callback is None:
                        dead_subs.append((sub,))
                        continue
                else:
                    callback = sub.callback

                callback(event)

            except Exception as e:
                logger.error(f"[SignalBus] Handler error for {event.topic}: {e}")

        # Clean up dead weak refs
        for pattern, subs in self._subscriptions.items():
            for (sub,) in dead_subs:
                if sub in subs:
                    subs.remove(sub)

    # ========================================================================
    # Legacy Signal Methods (Backward Compatibility)
    # ========================================================================

    def _emit_devices_internal(self, data: Any) -> None:
        """Internal: emit after throttle."""
        if isinstance(data, SignalEvent):
            self.devices_updated.emit(data.data)
        else:
            self.devices_updated.emit(data)

    def _emit_gantt_internal(self, data: Any) -> None:
        """Internal: emit after throttle."""
        if isinstance(data, SignalEvent):
            self.gantt_updated.emit(data.data)
        else:
            self.gantt_updated.emit(data)

    def emit_devices(
        self,
        data: Dict[str, Any],
        priority: SignalPriority = SignalPriority.NORMAL,
    ) -> None:
        """Emit device update signal (throttled)."""
        self._devices_throttler.push(data, priority)

    def emit_devices_immediate(self, data: Dict[str, Any]) -> None:
        """Emit device update immediately (bypasses throttle)."""
        self._devices_throttler.flush_now()
        self.devices_updated.emit(data)

    def emit_gantt(
        self,
        data: Dict[str, Any],
        priority: SignalPriority = SignalPriority.NORMAL,
    ) -> None:
        """Emit gantt update signal (throttled)."""
        self._gantt_throttler.push(data, priority)

    def emit_gantt_immediate(self, data: Dict[str, Any]) -> None:
        """Emit gantt update immediately (bypasses throttle)."""
        self._gantt_throttler.flush_now()
        self.gantt_updated.emit(data)

    def emit_error(self, message: str) -> None:
        """Emit error signal."""
        logger.error(f"[SignalBus] Error: {message}")
        self.error_occurred.emit(message)
        self.emit("error", message, SignalPriority.HIGH)

    def emit_loading(self, is_loading: bool) -> None:
        """Emit loading state signal."""
        self.loading_changed.emit(is_loading)
        self.emit("loading", is_loading)

    def emit_theme(self, theme: str) -> None:
        """Emit theme change signal."""
        self.theme_changed.emit(theme)
        self.emit("theme.changed", theme)

    def emit_page_change(self, page: str) -> None:
        """Emit page change signal."""
        self.page_changed.emit(page)
        self.emit("page.changed", page)

    def emit_device_selected(self, device_id: str) -> None:
        """Emit device selection signal."""
        self.device_selected.emit(device_id)
        self.emit("device.selected", device_id)

    def emit_device_deselected(self) -> None:
        """Emit device deselection signal."""
        self.device_deselected.emit()
        self.emit("device.deselected", None)

    # ========================================================================
    # Utilities
    # ========================================================================

    def flush_all(self) -> None:
        """Force flush all throttled signals."""
        self._devices_throttler.flush_now()
        self._gantt_throttler.flush_now()
        for throttler in self._throttlers.values():
            throttler.flush_now()

    def get_stats(self) -> Dict[str, Any]:
        """Get signal bus statistics."""
        return {
            "total_emits": self._emit_count,
            "topic_counts": self._topic_counts.copy(),
            "subscription_count": sum(len(subs) for subs in self._subscriptions.values()),
            "devices_throttler": self._devices_throttler.stats,
            "gantt_throttler": self._gantt_throttler.stats,
        }

    def clear_subscriptions(self) -> None:
        """Clear all subscriptions (for testing)."""
        self._subscriptions.clear()


def get_signal_bus() -> SignalBus:
    """Get the singleton signal bus instance."""
    return SignalBus()


__all__ = [
    "SignalBus",
    "SignalThrottler",
    "SignalEvent",
    "SignalPriority",
    "TopicFilter",
    "get_signal_bus",
]
