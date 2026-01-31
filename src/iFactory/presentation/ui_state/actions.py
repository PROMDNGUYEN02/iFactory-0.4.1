"""
Redux Actions for Presentation State.
Explicit intent definitions for the UI layer.
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


class UIActionType(Enum):
    """Enumeration of all possible UI state transitions."""

    THEME_CHANGED = "THEME_CHANGED"
    PAGE_NAVIGATED = "PAGE_NAVIGATED"
    MENU_ITEM_SELECTED = "MENU_ITEM_SELECTED"

    # Data Loading
    DEVICES_LOADED = "DEVICES_LOADED"
    GANTT_LOADED = "GANTT_LOADED"
    LOADING_STARTED = "LOADING_STARTED"
    LOADING_FINISHED = "LOADING_FINISHED"
    ERROR_OCCURRED = "ERROR_OCCURRED"

    # User Interactions
    LEFT_MENU_TOGGLED = "LEFT_MENU_TOGGLED"
    RIGHT_PANEL_TOGGLED = "RIGHT_PANEL_TOGGLED"
    DEVICE_SELECTED = "DEVICE_SELECTED"
    SET_DATA_RANGE = "SET_DATA_RANGE"

    # System
    SYSTEM_STATUS_UPDATED = "SYSTEM_STATUS_UPDATED"


@dataclass
class Action:
    """Immutable action payload."""

    type: str
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.now)


def change_theme(mode: str) -> Action:
    return Action(type=UIActionType.THEME_CHANGED.value, payload={"mode": mode})


def navigate_page(page_name: str) -> Action:
    # Determine menu index based on page name convention
    menu_index = 0
    if "orders" in page_name:
        menu_index = 1
    elif "settings" in page_name:
        menu_index = -1

    return Action(type=UIActionType.PAGE_NAVIGATED.value, payload={"page": page_name, "menu_index": menu_index})


def select_device(device_id: str) -> Action:
    return Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id})


def toggle_left_menu() -> Action:
    return Action(type=UIActionType.LEFT_MENU_TOGGLED.value)


def toggle_right_panel() -> Action:
    return Action(type=UIActionType.RIGHT_PANEL_TOGGLED.value)


def set_data_range(days: int) -> Action:
    return Action(type=UIActionType.SET_DATA_RANGE.value, payload=days)


def load_devices(view_models: Dict[str, Any]) -> Action:
    return Action(type=UIActionType.DEVICES_LOADED.value, payload=view_models)


def load_gantt(timeline_data: Dict[str, Any]) -> Action:
    return Action(type=UIActionType.GANTT_LOADED.value, payload=timeline_data)


def set_loading(is_loading: bool) -> Action:
    type_ = UIActionType.LOADING_STARTED if is_loading else UIActionType.LOADING_FINISHED
    return Action(type=type_.value)


def set_error(message: str) -> Action:
    return Action(type=UIActionType.ERROR_OCCURRED.value, payload={"message": message})


def update_system_status(mssql: bool, sqlite: bool, message: str = None) -> Action:
    return Action(type=UIActionType.SYSTEM_STATUS_UPDATED.value, payload={"mssql": mssql, "sqlite": sqlite, "message": message})
