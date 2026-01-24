"""
UI State Manager - Centralized UI State Management.

Provides a single source of truth for UI state across the application.
Ensures consistency and enables proper state propagation.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class LoadingState(Enum):
    """Loading state enumeration."""

    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class DeviceUIState:
    """UI state for a device."""

    device_id: str
    status_code: str = "0"
    status_display: str = "Unknown"
    status_color: str = "#808080"
    is_running: bool = False
    requires_attention: bool = False
    last_update: Optional[str] = None


@dataclass(frozen=True, slots=True)
class GanttUIState:
    """UI state for Gantt chart."""

    device_id: str
    frame_name: str
    segments: List[tuple] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    loading_state: LoadingState = LoadingState.IDLE


@dataclass(frozen=True, slots=True)
class PanelUIState:
    """UI state for panels."""

    is_visible: bool = False
    panel_type: str = "none"
    current_device: Optional[str] = None
    current_history_type: str = "summary"
    loading_state: LoadingState = LoadingState.IDLE


@dataclass(frozen=True, slots=True)
class GlobalUIState:
    """
    Global UI state container.

    Immutable state object that represents the entire UI state.
    Use `with_*` methods to create updated copies.
    """

    theme_mode: str = "light"
    current_page: str = "daboard_page"
    left_menu_expanded: bool = False
    right_panel_state: PanelUIState = field(default_factory=PanelUIState)
    devices: Dict[str, DeviceUIState] = field(default_factory=dict)
    gantt_charts: Dict[str, GanttUIState] = field(default_factory=dict)
    global_loading: bool = False

    def with_theme(self, theme: str) -> GlobalUIState:
        """Create copy with new theme."""
        return replace(self, theme_mode=theme)

    def with_page(self, page: str) -> GlobalUIState:
        """Create copy with new page."""
        return replace(self, current_page=page)

    def with_menu_expanded(self, expanded: bool) -> GlobalUIState:
        """Create copy with menu state."""
        return replace(self, left_menu_expanded=expanded)

    def with_right_panel(self, panel_state: PanelUIState) -> GlobalUIState:
        """Create copy with right panel state."""
        return replace(self, right_panel_state=panel_state)

    def with_device_state(self, device_id: str, state: DeviceUIState) -> GlobalUIState:
        """Create copy with updated device state."""
        new_devices = {**self.devices, device_id: state}
        return replace(self, devices=new_devices)

    def with_gantt_state(self, frame_name: str, state: GanttUIState) -> GlobalUIState:
        """Create copy with updated Gantt state."""
        new_gantt = {**self.gantt_charts, frame_name: state}
        return replace(self, gantt_charts=new_gantt)

    def with_global_loading(self, loading: bool) -> GlobalUIState:
        """Create copy with global loading state."""
        return replace(self, global_loading=loading)


class UIStateManager(QObject):
    """
    Centralized UI State Manager.

    Responsibilities:
        - Maintain single source of truth for UI state
        - Emit state change signals
        - Provide state queries
        - Track loading states across components

    Usage:
        ```python
        state_manager = UIStateManager()

        # Update state
        new_state = state_manager.state.with_theme("dark")
        state_manager.update_state(new_state)

        # Listen to changes
        state_manager.state_changed.connect(on_state_changed)

        # Query state
        is_dark = state_manager.state.theme_mode == "dark"
        ```
    """

    state_changed = Signal(object)
    loading_state_changed = Signal(str, LoadingState)
    device_state_changed = Signal(str, object)
    gantt_state_changed = Signal(str, object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = GlobalUIState()
        self._loading_states: Dict[str, LoadingState] = {}
        logger.debug("[UIStateManager] Created")

    @property
    def state(self) -> GlobalUIState:
        """Get current UI state."""
        return self._state

    def update_state(self, new_state: GlobalUIState) -> None:
        """
        Update entire UI state.

        Args:
            new_state: New global state
        """
        if new_state == self._state:
            return
        self._state = new_state
        self.state_changed.emit(new_state)
        logger.debug(f"[UIStateManager] State updated")

    def set_theme(self, theme: str) -> None:
        """Update theme mode."""
        new_state = self._state.with_theme(theme)
        self.update_state(new_state)

    def set_page(self, page: str) -> None:
        """Update current page."""
        new_state = self._state.with_page(page)
        self.update_state(new_state)

    def set_menu_expanded(self, expanded: bool) -> None:
        """Update menu expansion state."""
        new_state = self._state.with_menu_expanded(expanded)
        self.update_state(new_state)

    def set_right_panel(self, panel_state: PanelUIState) -> None:
        """Update right panel state."""
        new_state = self._state.with_right_panel(panel_state)
        self.update_state(new_state)

    def update_device_state(self, device_id: str, device_state: DeviceUIState) -> None:
        """Update single device state."""
        new_state = self._state.with_device_state(device_id, device_state)
        self.update_state(new_state)
        self.device_state_changed.emit(device_id, device_state)

    def update_gantt_state(self, frame_name: str, gantt_state: GanttUIState) -> None:
        """Update single Gantt chart state."""
        new_state = self._state.with_gantt_state(frame_name, gantt_state)
        self.update_state(new_state)
        self.gantt_state_changed.emit(frame_name, gantt_state)

    def set_loading(self, component: str, loading: bool) -> None:
        """
        Set loading state for a component.

        Args:
            component: Component identifier (e.g., "gantt_daboard_midle_frame_2")
            loading: Whether component is loading
        """
        state = LoadingState.LOADING if loading else LoadingState.IDLE
        self._loading_states[component] = state
        self.loading_state_changed.emit(component, state)
        logger.debug(f"[UIStateManager] {component} loading: {loading}")

    def get_loading_state(self, component: str) -> LoadingState:
        """Get loading state for component."""
        return self._loading_states.get(component, LoadingState.IDLE)

    def get_device_state(self, device_id: str) -> Optional[DeviceUIState]:
        """Get device state."""
        return self._state.devices.get(device_id)

    def get_gantt_state(self, frame_name: str) -> Optional[GanttUIState]:
        """Get Gantt state."""
        return self._state.gantt_charts.get(frame_name)


__all__ = [
    "UIStateManager",
    "GlobalUIState",
    "DeviceUIState",
    "GanttUIState",
    "PanelUIState",
    "LoadingState",
]
