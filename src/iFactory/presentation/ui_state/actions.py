"""Redux Actions for Presentation State."""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass


class UIActionType(Enum):
    """All UI action types."""

    THEME_CHANGED = "THEME_CHANGED"
    PAGE_NAVIGATED = "PAGE_NAVIGATED"
    MENU_ITEM_SELECTED = "MENU_ITEM_SELECTED"
    DEVICES_LOADED = "DEVICES_LOADED"
    GANTT_LOADED = "GANTT_LOADED"
    LEFT_MENU_TOGGLED = "LEFT_MENU_TOGGLED"
    RIGHT_PANEL_TOGGLED = "RIGHT_PANEL_TOGGLED"
    SYSTEM_STATUS_UPDATED = "SYSTEM_STATUS_UPDATED"
    DEVICE_SELECTED = "DEVICE_SELECTED"
    LOADING_STARTED = "LOADING_STARTED"
    LOADING_FINISHED = "LOADING_FINISHED"
    ERROR_OCCURRED = "ERROR_OCCURRED"


@dataclass
class Action:
    """Action with type and payload."""

    type: str
    payload: Optional[Any] = None


def change_theme(mode: str) -> Action:
    """Create theme change action."""
    return Action(type=UIActionType.THEME_CHANGED.value, payload={"mode": mode})


def load_devices(view_models: dict) -> Action:
    """Create devices loaded action."""
    return Action(type=UIActionType.DEVICES_LOADED.value, payload=view_models)


def load_gantt(timeline_data: dict) -> Action:
    """Create gantt loaded action."""
    return Action(type=UIActionType.GANTT_LOADED.value, payload=timeline_data)


def navigate_page(page_name: str) -> Action:
    """Create navigation action with menu index."""
    menu_index = 0  # Default to Dashboard
    if "orders" in page_name:
        menu_index = 1
    elif "settings" in page_name:
        menu_index = -1  # Special for settings

    return Action(type=UIActionType.PAGE_NAVIGATED.value, payload={"page": page_name, "menu_index": menu_index})


def select_menu_item(index: int) -> Action:
    """Create menu selection action."""
    return Action(type=UIActionType.MENU_ITEM_SELECTED.value, payload={"menu_index": index})


def update_system_status(mssql: bool, sqlite: bool, message: str = None) -> Action:
    return Action(type=UIActionType.SYSTEM_STATUS_UPDATED.value, payload={"mssql": mssql, "sqlite": sqlite, "message": message})


def select_device(device_id: str) -> Action:
    """Create device selection action."""
    return Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id})


def set_loading(is_loading: bool) -> Action:
    """Create loading state action."""
    action_type = UIActionType.LOADING_STARTED if is_loading else UIActionType.LOADING_FINISHED
    return Action(type=action_type.value)


def set_error(message: str) -> Action:
    """Create error action."""
    return Action(type=UIActionType.ERROR_OCCURRED.value, payload={"message": message})


__all__ = [
    "UIActionType",
    "Action",
    "change_theme",
    "load_devices",
    "load_gantt",
    "navigate_page",
    "select_menu_item",
    "select_device",
    "set_loading",
    "set_error",
]
