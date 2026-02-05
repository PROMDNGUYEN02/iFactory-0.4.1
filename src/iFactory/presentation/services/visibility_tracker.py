# File: src/iFactory/presentation/services/visibility_tracker.py
"""
Visibility Tracker - Track which devices are visible in viewport.

Features:
1. Track visible devices in each canvas
2. Debounced visibility change events
3. Priority loading for visible items
4. Scroll-aware lazy loading
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, QRectF, QTimer, Signal, Slot

logger = logging.getLogger(__name__)


# ============================================================================
# Visibility State
# ============================================================================


@dataclass
class VisibilityState:
    """State of visible items in a viewport."""

    visible_ids: FrozenSet[str] = field(default_factory=frozenset)
    viewport_rect: Optional[QRectF] = None
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def count(self) -> int:
        return len(self.visible_ids)

    def diff(self, other: "VisibilityState") -> Tuple[Set[str], Set[str]]:
        """
        Get difference between states.

        Returns:
            (newly_visible, no_longer_visible)
        """
        newly_visible = set(self.visible_ids) - set(other.visible_ids)
        no_longer_visible = set(other.visible_ids) - set(self.visible_ids)
        return newly_visible, no_longer_visible


# ============================================================================
# Visibility Tracker
# ============================================================================


class VisibilityTracker(QObject):
    """
    Tracks which devices are visible in viewports.

    Features:
    - Multi-viewport support (electrode, assembly canvases)
    - Debounced visibility change events
    - Priority queue for visible items
    - Integration with data loading

    Usage:
        tracker = VisibilityTracker()
        tracker.visibilityChanged.connect(on_visibility_changed)

        # Update visibility from canvas
        tracker.update_visibility("electrode", visible_device_ids)

        # Get visible devices for loading
        visible = tracker.get_visible_devices("electrode")
    """

    # Signals
    visibilityChanged = Signal(str, list)  # area_key, list of visible device_ids
    devicesNeedLoading = Signal(str, list)  # area_key, list of device_ids to load

    # Configuration
    DEBOUNCE_MS = 150  # Debounce visibility updates

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # State per area
        self._states: Dict[str, VisibilityState] = {}

        # Pending visibility changes (for debouncing)
        self._pending_updates: Dict[str, Set[str]] = {}

        # Timers for debouncing
        self._debounce_timers: Dict[str, QTimer] = {}

        # Track when devices became visible
        self._visible_since: Dict[str, Dict[str, datetime]] = {}

        # Track loaded devices per area
        self._loaded_devices: Dict[str, Set[str]] = {}

        # Active area (current page)
        self._active_area: Optional[str] = None

        logger.debug("[VisibilityTracker] Initialized")

    # ========================================================================
    # Public API
    # ========================================================================

    def set_active_area(self, area_key: str) -> None:
        """Set the active area (current page)."""
        if self._active_area != area_key:
            self._active_area = area_key
            logger.debug(f"[VisibilityTracker] Active area: {area_key}")

    def update_visibility(
        self,
        area_key: str,
        visible_ids: List[str],
        viewport_rect: Optional[QRectF] = None,
    ) -> None:
        """
        Update visible devices for an area.

        This is called by the canvas when viewport changes (scroll, resize).

        Args:
            area_key: Identifier for the viewport area
            visible_ids: List of device IDs currently visible
            viewport_rect: Optional viewport rectangle
        """
        # Only process active area
        if self._active_area and area_key != self._active_area:
            return

        # Store pending update
        self._pending_updates[area_key] = set(visible_ids)

        # Debounce the update
        if area_key not in self._debounce_timers:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda a=area_key: self._process_update(a))
            self._debounce_timers[area_key] = timer

        timer = self._debounce_timers[area_key]
        timer.stop()
        timer.start(self.DEBOUNCE_MS)

    def get_visible_devices(self, area_key: str) -> List[str]:
        """Get currently visible device IDs for an area."""
        state = self._states.get(area_key)
        if state:
            return list(state.visible_ids)
        return []

    def get_all_visible_devices(self) -> List[str]:
        """Get all visible devices across all areas (deduplicated)."""
        all_visible: Set[str] = set()
        for state in self._states.values():
            all_visible.update(state.visible_ids)
        return list(all_visible)

    def get_active_visible_devices(self) -> List[str]:
        """Get visible devices for active area only."""
        if self._active_area:
            return self.get_visible_devices(self._active_area)
        return self.get_all_visible_devices()

    def is_device_visible(self, device_id: str, area_key: Optional[str] = None) -> bool:
        """Check if a device is currently visible."""
        if area_key:
            state = self._states.get(area_key)
            return state is not None and device_id in state.visible_ids

        for state in self._states.values():
            if device_id in state.visible_ids:
                return True
        return False

    def get_devices_to_load(
        self,
        area_key: str,
        already_loaded: Optional[Set[str]] = None,
    ) -> List[str]:
        """
        Get devices that should be loaded (visible but not yet loaded).

        Args:
            area_key: Area to check
            already_loaded: Set of device IDs already loaded

        Returns:
            List of device IDs to load, prioritized by visibility duration
        """
        state = self._states.get(area_key)
        if not state:
            return []

        # Use provided or internal tracking
        if already_loaded is None:
            already_loaded = self._loaded_devices.get(area_key, set())

        to_load = set(state.visible_ids) - already_loaded

        if not to_load:
            return []

        # Prioritize by how long they've been visible
        visible_since = self._visible_since.get(area_key, {})
        now = datetime.now()

        def priority(device_id: str) -> float:
            visible_time = visible_since.get(device_id)
            if not visible_time:
                return 0
            return (now - visible_time).total_seconds()

        return sorted(to_load, key=priority, reverse=True)

    def mark_devices_loaded(self, area_key: str, device_ids: List[str]) -> None:
        """Mark devices as loaded (won't request again until cleared)."""
        if area_key not in self._loaded_devices:
            self._loaded_devices[area_key] = set()
        self._loaded_devices[area_key].update(device_ids)

    def clear_loaded_devices(self, area_key: Optional[str] = None) -> None:
        """Clear loaded device tracking."""
        if area_key:
            self._loaded_devices.pop(area_key, None)
        else:
            self._loaded_devices.clear()

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _process_update(self, area_key: str) -> None:
        """Process a debounced visibility update."""
        pending = self._pending_updates.pop(area_key, set())
        if not pending and area_key not in self._states:
            return

        # Get old state
        old_state = self._states.get(area_key, VisibilityState())

        # Create new state
        new_state = VisibilityState(
            visible_ids=frozenset(pending),
            last_update=datetime.now(),
        )

        # Store new state
        self._states[area_key] = new_state

        # Calculate diff
        newly_visible, no_longer_visible = new_state.diff(old_state)

        # Update visible_since tracking
        if area_key not in self._visible_since:
            self._visible_since[area_key] = {}

        now = datetime.now()
        for device_id in newly_visible:
            self._visible_since[area_key][device_id] = now

        for device_id in no_longer_visible:
            self._visible_since[area_key].pop(device_id, None)

        # Emit visibility changed if there's a difference
        if newly_visible or no_longer_visible:
            logger.debug(f"[VisibilityTracker] {area_key}: " f"+{len(newly_visible)} -{len(no_longer_visible)} " f"= {new_state.count} visible")
            self.visibilityChanged.emit(area_key, list(new_state.visible_ids))

            # Check if new devices need loading
            if newly_visible:
                loaded = self._loaded_devices.get(area_key, set())
                to_load = list(newly_visible - loaded)
                if to_load:
                    self.devicesNeedLoading.emit(area_key, to_load)

    # ========================================================================
    # Cleanup
    # ========================================================================

    def clear(self, area_key: Optional[str] = None) -> None:
        """Clear tracking state."""
        if area_key:
            self._states.pop(area_key, None)
            self._pending_updates.pop(area_key, None)
            self._visible_since.pop(area_key, None)
            self._loaded_devices.pop(area_key, None)

            if area_key in self._debounce_timers:
                self._debounce_timers[area_key].stop()
                del self._debounce_timers[area_key]
        else:
            self._states.clear()
            self._pending_updates.clear()
            self._visible_since.clear()
            self._loaded_devices.clear()

            for timer in self._debounce_timers.values():
                timer.stop()
            self._debounce_timers.clear()

    def dispose(self) -> None:
        """Clean up resources."""
        self.clear()
        self._active_area = None
        logger.debug("[VisibilityTracker] Disposed")


# ============================================================================
# Singleton Access
# ============================================================================

_tracker_instance: Optional[VisibilityTracker] = None


def get_visibility_tracker() -> VisibilityTracker:
    """Get the visibility tracker singleton."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = VisibilityTracker()
    return _tracker_instance


def reset_visibility_tracker() -> None:
    """Reset the visibility tracker (for testing)."""
    global _tracker_instance
    if _tracker_instance:
        _tracker_instance.dispose()
        _tracker_instance = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "VisibilityTracker",
    "VisibilityState",
    "get_visibility_tracker",
    "reset_visibility_tracker",
]
