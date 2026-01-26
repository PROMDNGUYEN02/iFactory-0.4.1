"""
Redux Actions for Presentation State.
"""

from enum import Enum
from .store import Action


class UIActionType(Enum):
    THEME_CHANGED = "THEME_CHANGED"
    PAGE_NAVIGATED = "PAGE_NAVIGATED"
    DEVICES_LOADED = "DEVICES_LOADED"
    LEFT_MENU_TOGGLED = "LEFT_MENU_TOGGLED"
    RIGHT_PANEL_TOGGLED = "RIGHT_PANEL_TOGGLED"
    DEVICE_SELECTED = "DEVICE_SELECTED"


def change_theme(mode: str) -> Action:
    return Action(type=UIActionType.THEME_CHANGED.value, payload={"mode": mode})


def load_devices(view_models: dict) -> Action:
    return Action(type=UIActionType.DEVICES_LOADED.value, payload=view_models)


def navigate_page(page_name: str) -> Action:
    return Action(type=UIActionType.PAGE_NAVIGATED.value, payload={"page": page_name})


def select_device(device_id: str) -> Action:
    return Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id})


__all__ = ["UIActionType", "change_theme", "load_devices", "navigate_page", "select_device"]
