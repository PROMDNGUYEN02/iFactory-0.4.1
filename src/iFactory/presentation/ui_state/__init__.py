"""Redux-like UI State Management."""

from .store import Store, Action
from .actions import UIActionType, change_theme, load_devices, navigate_page, select_device
from .reducers import root_reducer
from .selectors import (
    select_theme,
    select_current_page,
    select_all_devices,
    select_factory_summary,
    select_gantt_timeline,
    select_selected_device_data,
)

__all__ = [
    "Store",
    "Action",
    "UIActionType",
    "change_theme",
    "load_devices",
    "navigate_page",
    "select_device",
    "root_reducer",
    "select_theme",
    "select_current_page",
    "select_all_devices",
    "select_factory_summary",
    "select_gantt_timeline",
    "select_selected_device_data",
]
