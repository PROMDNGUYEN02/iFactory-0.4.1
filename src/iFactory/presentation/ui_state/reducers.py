"""
Pure Reducers for UI State.
"""

from typing import Dict, Any
from .store import Action
from .actions import UIActionType


def root_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    """Handles global UI state transitions."""
    new_state = state.copy()

    if action.type == UIActionType.THEME_CHANGED.value:
        new_state["theme"] = action.payload.get("mode", "light")

    elif action.type == UIActionType.PAGE_NAVIGATED.value:
        new_state["current_page"] = action.payload.get("page", "daboard_page")

    elif action.type == UIActionType.DEVICES_LOADED.value:
        new_state["devices"] = action.payload

    elif action.type == UIActionType.LEFT_MENU_TOGGLED.value:
        new_state["left_menu_expanded"] = not state.get("left_menu_expanded", True)

    elif action.type == UIActionType.RIGHT_PANEL_TOGGLED.value:
        new_state["right_panel_expanded"] = not state.get("right_panel_expanded", False)

    elif action.type == UIActionType.DEVICE_SELECTED.value:
        new_state["selected_device_id"] = action.payload.get("id")

    return new_state


__all__ = ["root_reducer"]
