"""Redux Actions for Presentation State."""

from enum import Enum
from .store import Action


class UIActionType(Enum):
    THEME_CHANGED = "THEME_CHANGED"
    PAGE_NAVIGATED = "PAGE_NAVIGATED"
    DEVICES_LOADED = "DEVICES_LOADED"
    GANTT_LOADED = "GANTT_LOADED"
    LEFT_MENU_TOGGLED = "LEFT_MENU_TOGGLED"
    RIGHT_PANEL_TOGGLED = "RIGHT_PANEL_TOGGLED"
    DEVICE_SELECTED = "DEVICE_SELECTED"
    LOADING_STARTED = "LOADING_STARTED"
    LOADING_FINISHED = "LOADING_FINISHED"
    ERROR_OCCURRED = "ERROR_OCCURRED"


def change_theme(mode: str) -> Action:
    return Action(type=UIActionType.THEME_CHANGED.value, payload={"mode": mode})


def load_devices(view_models: dict) -> Action:
    return Action(type=UIActionType.DEVICES_LOADED.value, payload=view_models)


def load_gantt(timeline_data: dict) -> Action:
    return Action(type=UIActionType.GANTT_LOADED.value, payload=timeline_data)


def navigate_page(page_name: str) -> Action:
    return Action(type=UIActionType.PAGE_NAVIGATED.value, payload={"page": page_name})


def select_device(device_id: str) -> Action:
    return Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id})


def set_loading(is_loading: bool) -> Action:
    action_type = UIActionType.LOADING_STARTED if is_loading else UIActionType.LOADING_FINISHED
    return Action(type=action_type.value)


def set_error(message: str) -> Action:
    return Action(type=UIActionType.ERROR_OCCURRED.value, payload={"message": message})


__all__ = [
    "UIActionType",
    "change_theme",
    "load_devices",
    "load_gantt",
    "navigate_page",
    "select_device",
    "set_loading",
    "set_error",
]
