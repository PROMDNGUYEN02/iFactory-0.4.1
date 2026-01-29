"""Pure Reducers for UI State."""

from typing import Any, Dict
from .actions import UIActionType, Action

initial_state = {
    "theme": "light",
    "current_page": "daboard_page",
    "selected_menu_index": 0,
    "left_menu_expanded": False,
    "right_panel_expanded": False,
    "devices": {},
    "gantt_timeline": {},
    "selected_device_id": None,
    "is_loading": False,
    "last_error": None,
    "system_status": {"mssql": False, "sqlite": False},
    "last_log_message": "Initializing...",
    "data_range_days": 1,  # Default: 1 Day
}


def root_reducer(state: Dict[str, Any] = None, action: Action = None) -> Dict[str, Any]:
    """Handles global UI state transitions."""
    if state is None:
        state = initial_state

    new_state = state.copy()
    action_type = action.type if hasattr(action, "type") else str(action)
    payload = action.payload if hasattr(action, "payload") else {}

    if payload is None:
        payload = {}

    if action_type == UIActionType.THEME_CHANGED.value:
        new_state["theme"] = payload.get("mode", "light")

    elif action_type == UIActionType.PAGE_NAVIGATED.value:
        new_state["current_page"] = payload.get("page", "daboard_page")
        if "menu_index" in payload:
            new_state["selected_menu_index"] = payload["menu_index"]

    elif action_type == UIActionType.MENU_ITEM_SELECTED.value:
        new_state["selected_menu_index"] = payload.get("menu_index", 0)

    elif action_type == UIActionType.DEVICES_LOADED.value:
        new_state["devices"] = payload

    elif action_type == UIActionType.GANTT_LOADED.value:
        new_state["gantt_timeline"] = payload

    elif action_type == UIActionType.LEFT_MENU_TOGGLED.value:
        new_state["left_menu_expanded"] = not state.get("left_menu_expanded", True)

    elif action_type == UIActionType.RIGHT_PANEL_TOGGLED.value:
        new_state["right_panel_expanded"] = not state.get("right_panel_expanded", False)

    elif action_type == UIActionType.SYSTEM_STATUS_UPDATED.value:
        return {
            **state,
            "system_status": {"mssql": payload.get("mssql", False), "sqlite": payload.get("sqlite", False)},
            "last_log_message": payload.get("message", state.get("last_log_message")),
        }

    elif action_type == UIActionType.DEVICE_SELECTED.value:
        new_state["selected_device_id"] = payload.get("id")

    elif action_type == UIActionType.LOADING_STARTED.value:
        new_state["is_loading"] = True

    elif action_type == UIActionType.LOADING_FINISHED.value:
        new_state["is_loading"] = False

    elif action_type == UIActionType.ERROR_OCCURRED.value:
        new_state["last_error"] = payload.get("message")

    elif action_type == UIActionType.SET_DATA_RANGE.value:
        # Payload is integer days (1, 7, 30, 90)
        new_state["data_range_days"] = payload

    return new_state


__all__ = ["root_reducer"]
