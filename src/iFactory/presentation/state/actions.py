# File: presentation/state/actions.py
"""
State Actions.
Defines all possible state mutations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional


class ActionType(Enum):
    INIT = auto()
    SET_THEME = auto()
    SET_PAGE = auto()
    TOGGLE_SIDEBAR = auto()
    TOGGLE_RIGHT_PANEL = auto()
    SELECT_DEVICE = auto()
    SELECT_DEVICE_ONLY = auto()  # Select without opening panel
    DESELECT_DEVICE = auto()
    SET_DATA_RANGE = auto()
    SET_LOADING = auto()
    SET_ERROR = auto()
    CLEAR_ERROR = auto()
    LOAD_DEVICES = auto()
    UPDATE_DEVICES = auto()
    LOAD_GANTT = auto()
    SET_SELECTED_DEVICE_GANTT = auto()
    UPDATE_SYSTEM_STATUS = auto()
    SYNC_COMPLETED = auto()
    SET_PAGE_DEVICES = auto()


@dataclass(frozen=True)
class Action:
    type: ActionType
    payload: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)


def create_action(action_type: ActionType, payload: Any = None) -> Action:
    return Action(type=action_type, payload=payload)


def set_theme(theme: str) -> Action:
    return create_action(ActionType.SET_THEME, theme)


def set_page(page: str) -> Action:
    return create_action(ActionType.SET_PAGE, page)


def toggle_sidebar() -> Action:
    return create_action(ActionType.TOGGLE_SIDEBAR)


def toggle_right_panel() -> Action:
    return create_action(ActionType.TOGGLE_RIGHT_PANEL)


def select_device(device_id: str) -> Action:
    """Select device AND open right panel (double-click)."""
    return create_action(ActionType.SELECT_DEVICE, device_id)


def select_device_only(device_id: str) -> Action:
    """Select device WITHOUT opening right panel (single-click)."""
    return create_action(ActionType.SELECT_DEVICE_ONLY, device_id)


def deselect_device() -> Action:
    return create_action(ActionType.DESELECT_DEVICE)


def set_data_range(days: int) -> Action:
    return create_action(ActionType.SET_DATA_RANGE, days)


def set_loading(is_loading: bool) -> Action:
    return create_action(ActionType.SET_LOADING, is_loading)


def set_error(message: str) -> Action:
    return create_action(ActionType.SET_ERROR, message)


def clear_error() -> Action:
    return create_action(ActionType.CLEAR_ERROR)


def load_devices(devices: Dict[str, Any]) -> Action:
    """Replace all devices in state."""
    return create_action(ActionType.LOAD_DEVICES, devices)


def update_devices(devices: Dict[str, Any]) -> Action:
    """Merge/update devices in state (partial update)."""
    return create_action(ActionType.UPDATE_DEVICES, devices)


def load_gantt(gantt_data: Dict[str, Any]) -> Action:
    return create_action(ActionType.LOAD_GANTT, gantt_data)


def set_selected_device_gantt(gantt_view_model: Any) -> Action:
    return create_action(ActionType.SET_SELECTED_DEVICE_GANTT, gantt_view_model)


def update_system_status(mssql: bool, sqlite: bool, message: str = "") -> Action:
    return create_action(
        ActionType.UPDATE_SYSTEM_STATUS,
        {"mssql": mssql, "sqlite": sqlite, "message": message},
    )


def sync_completed(payload: Dict[str, Any]) -> Action:
    return create_action(ActionType.SYNC_COMPLETED, payload)


def set_page_devices(page: str, device_codes: list) -> Action:
    return create_action(ActionType.SET_PAGE_DEVICES, {"page": page, "devices": device_codes})


__all__ = [
    "ActionType",
    "Action",
    "create_action",
    "set_theme",
    "set_page",
    "toggle_sidebar",
    "toggle_right_panel",
    "select_device",
    "select_device_only",
    "deselect_device",
    "set_data_range",
    "set_loading",
    "set_error",
    "clear_error",
    "load_devices",
    "update_devices",
    "load_gantt",
    "set_selected_device_gantt",
    "update_system_status",
    "sync_completed",
    "set_page_devices",
]
