# src/iFactory/presentation/state/actions.py
"""
Type-safe Action System.

Features:
- Strongly typed action payloads
- Action creators with validation
- Backward compatible with dict payloads
- Union types for exhaustive handling
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import DeviceSnapshot, GanttSegment, ThemeMode, PageId


class ActionType(Enum):
    """All possible action types."""

    # Initialization
    INIT = auto()
    HYDRATE = auto()  # Restore persisted state

    # Theme
    SET_THEME = auto()
    TOGGLE_THEME = auto()

    # Navigation
    SET_PAGE = auto()

    # UI State
    TOGGLE_SIDEBAR = auto()
    SET_SIDEBAR = auto()
    TOGGLE_RIGHT_PANEL = auto()
    SET_RIGHT_PANEL = auto()
    SET_LOADING = auto()
    SET_ERROR = auto()
    CLEAR_ERROR = auto()

    # Selection
    SELECT_DEVICE = auto()
    SELECT_DEVICE_ONLY = auto()
    DESELECT_DEVICE = auto()
    SET_DEVICE_GANTT = auto()

    # Data
    LOAD_DEVICES = auto()
    UPDATE_DEVICE = auto()
    UPDATE_DEVICES = auto()
    REMOVE_DEVICE = auto()
    LOAD_GANTT = auto()
    SET_PAGE_DEVICES = auto()

    # Settings
    SET_DATA_RANGE = auto()

    # System
    UPDATE_SYSTEM_STATUS = auto()
    SYNC_STARTED = auto()
    SYNC_COMPLETED = auto()
    SYNC_FAILED = auto()


# ============================================================================
# Typed Payloads
# ============================================================================


@dataclass(frozen=True, slots=True)
class SetThemePayload:
    """Payload for SET_THEME action."""

    theme: str  # Will be converted to ThemeMode

    def __post_init__(self):
        if self.theme not in ("light", "dark"):
            object.__setattr__(self, "theme", "light")


@dataclass(frozen=True, slots=True)
class SetPagePayload:
    """Payload for SET_PAGE action."""

    page: str  # Will be converted to PageId


@dataclass(frozen=True, slots=True)
class SelectDevicePayload:
    """Payload for device selection actions."""

    device_id: str
    open_panel: bool = False  # True for SELECT_DEVICE, False for SELECT_DEVICE_ONLY


@dataclass(frozen=True, slots=True)
class SetDeviceGanttPayload:
    """Payload for SET_DEVICE_GANTT action."""

    device_id: str
    gantt_viewmodel: Any  # GanttChartViewModel reference


@dataclass(frozen=True, slots=True)
class LoadDevicesPayload:
    """Payload for LOAD_DEVICES action."""

    devices: Tuple["DeviceSnapshot", ...]

    @classmethod
    def from_dict(cls, devices_dict: Dict[str, Any]) -> "LoadDevicesPayload":
        """Create from dict for backward compatibility."""
        from .types import DeviceSnapshot

        snapshots = tuple(DeviceSnapshot.from_dict({**v, "device_id": k}) if isinstance(v, dict) else v for k, v in devices_dict.items())
        return cls(devices=snapshots)


@dataclass(frozen=True, slots=True)
class UpdateDevicePayload:
    """Payload for UPDATE_DEVICE action."""

    device_id: str
    updates: Dict[str, Any]


@dataclass(frozen=True, slots=True)
class LoadGanttPayload:
    """Payload for LOAD_GANTT action."""

    device_id: str
    segments: Tuple["GanttSegment", ...]


@dataclass(frozen=True, slots=True)
class SetPageDevicesPayload:
    """Payload for SET_PAGE_DEVICES action."""

    page: str
    device_ids: Tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SetDataRangePayload:
    """Payload for SET_DATA_RANGE action."""

    days: int

    def __post_init__(self):
        # Clamp to valid range
        clamped = max(1, min(self.days, 30))
        if clamped != self.days:
            object.__setattr__(self, "days", clamped)


@dataclass(frozen=True, slots=True)
class SystemStatusPayload:
    """Payload for UPDATE_SYSTEM_STATUS action."""

    mssql_connected: bool = False
    sqlite_connected: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class SyncCompletedPayload:
    """Payload for SYNC_COMPLETED action."""

    timestamp: datetime = field(default_factory=datetime.now)
    device_count: int = 0
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class SyncFailedPayload:
    """Payload for SYNC_FAILED action."""

    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True, slots=True)
class SetErrorPayload:
    """Payload for SET_ERROR action."""

    message: str
    code: Optional[str] = None


# Type alias for all payloads
ActionPayload = Union[
    None,
    str,
    int,
    bool,
    SetThemePayload,
    SetPagePayload,
    SelectDevicePayload,
    SetDeviceGanttPayload,
    LoadDevicesPayload,
    UpdateDevicePayload,
    LoadGanttPayload,
    SetPageDevicesPayload,
    SetDataRangePayload,
    SystemStatusPayload,
    SyncCompletedPayload,
    SyncFailedPayload,
    SetErrorPayload,
    Dict[str, Any],  # Backward compatibility
]


# ============================================================================
# Action Class
# ============================================================================


@dataclass(frozen=True, slots=True)
class Action:
    """
    Immutable action with typed payload.

    Actions describe what happened and carry the data needed
    to update state. They are processed by reducers.
    """

    type: ActionType
    payload: ActionPayload = None
    timestamp: datetime = field(default_factory=datetime.now)
    meta: Optional[Dict[str, Any]] = None  # For middleware use

    def __repr__(self) -> str:
        payload_str = ""
        if self.payload is not None:
            if isinstance(self.payload, str):
                payload_str = f"'{self.payload}'"
            elif isinstance(self.payload, dict):
                payload_str = f"{{...{len(self.payload)} keys}}"
            else:
                payload_str = type(self.payload).__name__
        return f"Action({self.type.name}, {payload_str})"


# ============================================================================
# Action Creators
# ============================================================================


def create_action(
    action_type: ActionType,
    payload: ActionPayload = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Action:
    """Generic action creator."""
    return Action(type=action_type, payload=payload, meta=meta)


# ----- Theme Actions -----


def set_theme(theme: str) -> Action:
    """Set application theme."""
    return Action(
        type=ActionType.SET_THEME,
        payload=SetThemePayload(theme=theme),
    )


def toggle_theme() -> Action:
    """Toggle between light and dark theme."""
    return Action(type=ActionType.TOGGLE_THEME)


# ----- Navigation Actions -----


def set_page(page: str) -> Action:
    """Navigate to a page."""
    return Action(
        type=ActionType.SET_PAGE,
        payload=SetPagePayload(page=page),
    )


# ----- UI State Actions -----


def toggle_sidebar() -> Action:
    """Toggle sidebar expansion."""
    return Action(type=ActionType.TOGGLE_SIDEBAR)


def set_sidebar(expanded: bool) -> Action:
    """Set sidebar expansion state."""
    return Action(type=ActionType.SET_SIDEBAR, payload=expanded)


def toggle_right_panel() -> Action:
    """Toggle right panel expansion."""
    return Action(type=ActionType.TOGGLE_RIGHT_PANEL)


def set_right_panel(expanded: bool) -> Action:
    """Set right panel expansion state."""
    return Action(type=ActionType.SET_RIGHT_PANEL, payload=expanded)


def set_loading(is_loading: bool) -> Action:
    """Set loading state."""
    return Action(type=ActionType.SET_LOADING, payload=is_loading)


def set_error(message: str, code: Optional[str] = None) -> Action:
    """Set error state."""
    return Action(
        type=ActionType.SET_ERROR,
        payload=SetErrorPayload(message=message, code=code),
    )


def clear_error() -> Action:
    """Clear error state."""
    return Action(type=ActionType.CLEAR_ERROR)


# ----- Selection Actions -----


def select_device(device_id: str) -> Action:
    """Select device AND open right panel (double-click behavior)."""
    return Action(
        type=ActionType.SELECT_DEVICE,
        payload=SelectDevicePayload(device_id=device_id, open_panel=True),
    )


def select_device_only(device_id: str) -> Action:
    """Select device WITHOUT opening right panel (single-click behavior)."""
    return Action(
        type=ActionType.SELECT_DEVICE_ONLY,
        payload=SelectDevicePayload(device_id=device_id, open_panel=False),
    )


def deselect_device() -> Action:
    """Clear device selection."""
    return Action(type=ActionType.DESELECT_DEVICE)


def set_selected_device_gantt(gantt_viewmodel: Any) -> Action:
    """Set Gantt chart for selected device."""
    return Action(
        type=ActionType.SET_DEVICE_GANTT,
        payload=gantt_viewmodel,
    )


# ----- Data Actions -----


def load_devices(devices: Union[Dict[str, Any], Tuple]) -> Action:
    """
    Load/replace all devices.

    Accepts both dict (backward compat) and tuple of DeviceSnapshot.
    """
    if isinstance(devices, dict):
        payload = LoadDevicesPayload.from_dict(devices)
    else:
        payload = LoadDevicesPayload(devices=devices)

    return Action(type=ActionType.LOAD_DEVICES, payload=payload)


def update_devices(devices: Dict[str, Any]) -> Action:
    """Update/merge devices (partial update)."""
    return Action(type=ActionType.UPDATE_DEVICES, payload=devices)


def update_device(device_id: str, updates: Dict[str, Any]) -> Action:
    """Update a single device."""
    return Action(
        type=ActionType.UPDATE_DEVICE,
        payload=UpdateDevicePayload(device_id=device_id, updates=updates),
    )


def load_gantt(device_id: str, segments: List[Any]) -> Action:
    """Load Gantt segments for a device."""
    from .types import GanttSegment

    typed_segments = tuple(
        (
            GanttSegment(
                start_time=s.get("start_time") or s.start_time,
                end_time=s.get("end_time") or s.end_time,
                status_code=s.get("status_code") or s.status_code,
                status_name=s.get("status_name", "") or getattr(s, "status_name", ""),
            )
            if isinstance(s, dict)
            else s
        )
        for s in segments
    )

    return Action(
        type=ActionType.LOAD_GANTT,
        payload=LoadGanttPayload(device_id=device_id, segments=typed_segments),
    )


def set_page_devices(page: str, device_ids: List[str]) -> Action:
    """Set devices for a page."""
    return Action(
        type=ActionType.SET_PAGE_DEVICES,
        payload=SetPageDevicesPayload(page=page, device_ids=tuple(device_ids)),
    )


# ----- Settings Actions -----


def set_data_range(days: int) -> Action:
    """Set data range in days."""
    return Action(
        type=ActionType.SET_DATA_RANGE,
        payload=SetDataRangePayload(days=days),
    )


# ----- System Actions -----


def update_system_status(
    mssql: bool = False,
    sqlite: bool = False,
    message: str = "",
) -> Action:
    """Update system connection status."""
    return Action(
        type=ActionType.UPDATE_SYSTEM_STATUS,
        payload=SystemStatusPayload(
            mssql_connected=mssql,
            sqlite_connected=sqlite,
            message=message,
        ),
    )


def sync_started() -> Action:
    """Signal sync operation started."""
    return Action(type=ActionType.SYNC_STARTED)


def sync_completed(
    device_count: int = 0,
    duration_ms: float = 0.0,
) -> Action:
    """Signal sync operation completed successfully."""
    return Action(
        type=ActionType.SYNC_COMPLETED,
        payload=SyncCompletedPayload(
            device_count=device_count,
            duration_ms=duration_ms,
        ),
    )


def sync_failed(error_message: str) -> Action:
    """Signal sync operation failed."""
    return Action(
        type=ActionType.SYNC_FAILED,
        payload=SyncFailedPayload(error_message=error_message),
    )


# ============================================================================
# Batch Action Helper
# ============================================================================


def batch_actions(*actions: Action) -> List[Action]:
    """
    Create a list of actions to be dispatched together.

    Usage with store.batch():
        with store.batch():
            for action in batch_actions(a1, a2, a3):
                store.dispatch(action)
    """
    return list(actions)


__all__ = [
    # Enums
    "ActionType",
    # Payloads
    "SetThemePayload",
    "SetPagePayload",
    "SelectDevicePayload",
    "SetDeviceGanttPayload",
    "LoadDevicesPayload",
    "UpdateDevicePayload",
    "LoadGanttPayload",
    "SetPageDevicesPayload",
    "SetDataRangePayload",
    "SystemStatusPayload",
    "SyncCompletedPayload",
    "SyncFailedPayload",
    "SetErrorPayload",
    "ActionPayload",
    # Action class
    "Action",
    "create_action",
    # Action creators
    "set_theme",
    "toggle_theme",
    "set_page",
    "toggle_sidebar",
    "set_sidebar",
    "toggle_right_panel",
    "set_right_panel",
    "set_loading",
    "set_error",
    "clear_error",
    "select_device",
    "select_device_only",
    "deselect_device",
    "set_selected_device_gantt",
    "load_devices",
    "update_devices",
    "update_device",
    "load_gantt",
    "set_page_devices",
    "set_data_range",
    "update_system_status",
    "sync_started",
    "sync_completed",
    "sync_failed",
    "batch_actions",
]
