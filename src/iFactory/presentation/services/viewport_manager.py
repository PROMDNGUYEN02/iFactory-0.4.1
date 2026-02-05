# src/iFactory/presentation/services/viewport_manager.py
"""
Viewport Manager - Track visible devices and prefetch zones.

Responsibilities:
- Detect which devices are in viewport
- Track prefetch zone (200px ahead of viewport)
- Emit events when visibility changes
- Optimize rendering by pausing off-screen devices

Usage:
    manager = DeviceViewportManager(prefetch_distance=200)

    # On scroll
    change = manager.update_viewport(
        scroll_y=500,
        viewport_height=800,
        device_positions=[(id, y, height), ...],
    )

    # Handle changes
    for device_id in change.newly_visible:
        start_loading(device_id)

    for device_id in change.newly_hidden:
        pause_updates(device_id)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ViewportItem:
    """Position and visibility info for a device."""

    device_id: str
    top: int
    height: int
    is_visible: bool
    is_in_prefetch_zone: bool
    distance_from_viewport: int = 0  # Pixels above/below viewport

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class ViewportChange:
    """
    Changes detected after viewport update.

    Used to trigger appropriate actions:
    - newly_visible: Start high-priority loading
    - newly_hidden: Pause updates, keep in memory
    - entered_prefetch: Start low-priority background loading
    - left_prefetch: Cancel pending loads
    """

    newly_visible: List[str] = field(default_factory=list)
    newly_hidden: List[str] = field(default_factory=list)
    entered_prefetch: List[str] = field(default_factory=list)
    left_prefetch: List[str] = field(default_factory=list)

    still_visible: List[str] = field(default_factory=list)
    still_hidden: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if any changes occurred."""
        return bool(self.newly_visible or self.newly_hidden or self.entered_prefetch or self.left_prefetch)


class DeviceViewportManager:
    """
    Manages device visibility and prefetch strategy.

    Features:
    - Tracks visible devices in viewport
    - Manages prefetch zone (configurable distance ahead)
    - Detects visibility changes
    - Callbacks for visibility events
    - Memory-efficient state tracking

    Zones:
        Visible Zone: [scroll_y, scroll_y + viewport_height]
        → Active rendering, real-time updates

        Prefetch Zone: [scroll_y + viewport_height, scroll_y + viewport_height + prefetch_distance]
        → Background loading, low priority

        Outside Zone: Everything else
        → Paused updates, cached in memory
    """

    def __init__(
        self,
        prefetch_distance: int = 200,
        enable_prefetch: bool = True,
    ):
        self._prefetch_distance = prefetch_distance
        self._enable_prefetch = enable_prefetch

        # Current state
        self._viewport_state: Dict[str, ViewportItem] = {}
        self._visible_devices: Set[str] = set()
        self._prefetch_devices: Set[str] = set()

        # Callbacks
        self._on_visible_changed: List[Callable[[ViewportChange], None]] = []
        self._on_prefetch_changed: List[Callable[[List[str]], None]] = []

        logger.info(
            "[ViewportManager] Initialized with prefetch_distance=%dpx",
            prefetch_distance,
        )

    def update_viewport(
        self,
        scroll_y: int,
        viewport_height: int,
        device_positions: List[Tuple[str, int, int]],  # (id, top, height)
    ) -> ViewportChange:
        """
        Update viewport state and detect changes.

        Args:
            scroll_y: Current scroll position (pixels from top)
            viewport_height: Height of visible area
            device_positions: List of (device_id, top_position, height)

        Returns:
            ViewportChange with detected changes

        Example:
            >>> change = manager.update_viewport(
            ...     scroll_y=500,
            ...     viewport_height=800,
            ...     device_positions=[
            ...         ("DEV01", 400, 60),  # Visible
            ...         ("DEV02", 1200, 60), # In prefetch
            ...         ("DEV03", 2000, 60), # Outside
            ...     ],
            ... )
            >>> print(change.newly_visible)
            ['DEV01']
        """
        viewport_bottom = scroll_y + viewport_height
        prefetch_bottom = viewport_bottom + self._prefetch_distance

        # Track previous state
        prev_visible = self._visible_devices.copy()
        prev_prefetch = self._prefetch_devices.copy()

        # Compute new state
        new_state: Dict[str, ViewportItem] = {}
        new_visible: Set[str] = set()
        new_prefetch: Set[str] = set()

        for device_id, top, height in device_positions:
            bottom = top + height

            # Check visibility
            is_visible = top < viewport_bottom and bottom > scroll_y

            # Check prefetch zone
            is_in_prefetch = False
            if self._enable_prefetch and not is_visible:
                is_in_prefetch = top < prefetch_bottom and bottom > viewport_bottom

            # Calculate distance from viewport
            if is_visible:
                distance = 0
            elif top >= viewport_bottom:
                distance = top - viewport_bottom  # Below viewport
            else:
                distance = scroll_y - bottom  # Above viewport

            # Create item
            item = ViewportItem(
                device_id=device_id,
                top=top,
                height=height,
                is_visible=is_visible,
                is_in_prefetch_zone=is_in_prefetch,
                distance_from_viewport=distance,
            )

            new_state[device_id] = item

            if is_visible:
                new_visible.add(device_id)
            elif is_in_prefetch:
                new_prefetch.add(device_id)

        # Detect changes
        change = ViewportChange(
            newly_visible=list(new_visible - prev_visible),
            newly_hidden=list(prev_visible - new_visible),
            entered_prefetch=list(new_prefetch - prev_prefetch),
            left_prefetch=list(prev_prefetch - new_prefetch),
            still_visible=list(new_visible & prev_visible),
            still_hidden=list(set(new_state.keys()) - new_visible - new_prefetch),
        )

        # Update state
        self._viewport_state = new_state
        self._visible_devices = new_visible
        self._prefetch_devices = new_prefetch

        # Notify callbacks
        if change.has_changes:
            self._notify_visible_changed(change)

            if change.entered_prefetch or change.left_prefetch:
                self._notify_prefetch_changed(list(new_prefetch))

        # Log if significant changes
        if change.newly_visible or change.newly_hidden:
            logger.debug(
                "[ViewportManager] Visibility changed: " "+%d visible, -%d hidden, %d in prefetch",
                len(change.newly_visible),
                len(change.newly_hidden),
                len(new_prefetch),
            )

        return change

    def get_visible_devices(self) -> List[str]:
        """
        Get currently visible device IDs.

        These devices should have:
        - Active rendering
        - Real-time status updates
        - High priority data fetching
        """
        return list(self._visible_devices)

    def get_prefetch_devices(self) -> List[str]:
        """
        Get devices in prefetch zone.

        These devices should have:
        - Background data fetching
        - Low priority loading
        - Prepared for becoming visible
        """
        return list(self._prefetch_devices)

    def get_hidden_devices(self) -> List[str]:
        """
        Get devices outside viewport and prefetch zone.

        These devices should have:
        - Paused updates
        - Cached data in memory
        - No active rendering
        """
        all_devices = set(self._viewport_state.keys())
        return list(all_devices - self._visible_devices - self._prefetch_devices)

    def is_device_visible(self, device_id: str) -> bool:
        """Check if specific device is visible."""
        return device_id in self._visible_devices

    def is_device_in_prefetch(self, device_id: str) -> bool:
        """Check if specific device is in prefetch zone."""
        return device_id in self._prefetch_devices

    def get_device_item(self, device_id: str) -> Optional[ViewportItem]:
        """Get viewport item for device."""
        return self._viewport_state.get(device_id)

    def get_visible_sorted_by_distance(self) -> List[Tuple[str, int]]:
        """
        Get visible devices sorted by distance from top of viewport.

        Returns:
            List of (device_id, distance) tuples, sorted nearest first

        Useful for:
        - Prioritizing loading order
        - Optimizing rendering order
        """
        items = [(device_id, item) for device_id, item in self._viewport_state.items() if item.is_visible]

        items.sort(key=lambda x: x[1].top)

        return [(device_id, item.top) for device_id, item in items]

    # ========================================================================
    # Callbacks
    # ========================================================================

    def on_visible_changed(
        self,
        callback: Callable[[ViewportChange], None],
    ) -> None:
        """Register callback for visibility changes."""
        self._on_visible_changed.append(callback)

    def on_prefetch_changed(
        self,
        callback: Callable[[List[str]], None],
    ) -> None:
        """Register callback for prefetch zone changes."""
        self._on_prefetch_changed.append(callback)

    def _notify_visible_changed(self, change: ViewportChange) -> None:
        """Notify visibility change callbacks."""
        for callback in self._on_visible_changed:
            try:
                callback(change)
            except Exception as e:
                logger.error(f"[ViewportManager] Callback error: {e}")

    def _notify_prefetch_changed(self, prefetch_devices: List[str]) -> None:
        """Notify prefetch change callbacks."""
        for callback in self._on_prefetch_changed:
            try:
                callback(prefetch_devices)
            except Exception as e:
                logger.error(f"[ViewportManager] Callback error: {e}")

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, int]:
        """Get viewport statistics."""
        return {
            "total_devices": len(self._viewport_state),
            "visible_count": len(self._visible_devices),
            "prefetch_count": len(self._prefetch_devices),
            "hidden_count": len(self.get_hidden_devices()),
        }

    def clear(self) -> None:
        """Clear all state."""
        self._viewport_state.clear()
        self._visible_devices.clear()
        self._prefetch_devices.clear()


__all__ = [
    "DeviceViewportManager",
    "ViewportChange",
    "ViewportItem",
]
