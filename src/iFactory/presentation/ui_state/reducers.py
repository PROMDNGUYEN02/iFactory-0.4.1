"""Pure Reducers for UI State."""

from typing import Any, Dict

from .store import Action
from .actions import UIActionType


def root_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    """Handles global UI state transitions."""
    new_state = state.copy()

    match action.type:
        case UIActionType.THEME_CHANGED.value:
            new_state["theme"] = action.payload.get("mode", "light")

        case UIActionType.PAGE_NAVIGATED.value:
            new_state["current_page"] = action.payload.get("page", "daboard_page")

        case UIActionType.DEVICES_LOADED.value:
            new_state["devices"] = action.payload

        case UIActionType.GANTT_LOADED.value:
            new_state["gantt_timeline"] = action.payload

        case UIActionType.LEFT_MENU_TOGGLED.value:
            new_state["left_menu_expanded"] = not state.get("left_menu_expanded", True)

        case UIActionType.RIGHT_PANEL_TOGGLED.value:
            new_state["right_panel_expanded"] = not state.get("right_panel_expanded", False)

        case UIActionType.DEVICE_SELECTED.value:
            new_state["selected_device_id"] = action.payload.get("id")

        case UIActionType.LOADING_STARTED.value:
            new_state["is_loading"] = True

        case UIActionType.LOADING_FINISHED.value:
            new_state["is_loading"] = False

        case UIActionType.ERROR_OCCURRED.value:
            new_state["last_error"] = action.payload.get("message")

    return new_state


__all__ = ["root_reducer"]
