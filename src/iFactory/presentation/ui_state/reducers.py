"""
Redux Reducers.
Pure functions that take the current state and an action, returning a new state.
"""

from typing import Any, Dict
from .actions import UIActionType

# --- INITIAL STATE DEFINITION ---
INITIAL_STATE = {
    # Navigation
    "current_page": "daboard_page",  # FORCE DEFAULT DASHBOARD
    "left_menu_expanded": True,
    "right_panel_expanded": False,
    "theme": "light",
    # Selection
    "selected_device_id": None,
    "data_range_days": 1,
    # Data
    "devices": {},
    "gantt_timeline": {},
    "factory_summary": {"output": 0, "yield_rate": 0, "lost": 0},
    # System
    "is_loading": False,
    "last_error": None,
    "system_status": {"mssql": False, "sqlite": False},
    "last_log_message": "System Ready",
}


def root_reducer(state: Dict[str, Any] = None, action: Any = None) -> Dict[str, Any]:
    """
    Main reducer combining all sub-reducers.
    """
    if state is None:
        return INITIAL_STATE

    # Copy state to ensure immutability
    next_state = state.copy()
    payload = action.payload if action else None
    type_ = action.type if action else None

    # --- UI Interactions ---
    if type_ == UIActionType.THEME_CHANGED.value:
        next_state["theme"] = payload["mode"]

    elif type_ == UIActionType.PAGE_NAVIGATED.value:
        next_state["current_page"] = payload["page"]
        # Note: menu_index logic is handled in View, state only stores page ID

    elif type_ == UIActionType.LEFT_MENU_TOGGLED.value:
        next_state["left_menu_expanded"] = not next_state["left_menu_expanded"]

    elif type_ == UIActionType.RIGHT_PANEL_TOGGLED.value:
        next_state["right_panel_expanded"] = not next_state["right_panel_expanded"]

    elif type_ == UIActionType.DEVICE_SELECTED.value:
        next_state["selected_device_id"] = payload["id"]
        next_state["right_panel_expanded"] = True  # Auto-open panel

    elif type_ == UIActionType.SET_DATA_RANGE.value:
        next_state["data_range_days"] = payload

    # --- Data Loading ---
    elif type_ == UIActionType.DEVICES_LOADED.value:
        # payload is expected to be a Dict of DeviceViewModels
        next_state["devices"] = payload
        next_state["is_loading"] = False

    elif type_ == UIActionType.GANTT_LOADED.value:
        next_state["gantt_timeline"] = payload

    elif type_ == UIActionType.LOADING_STARTED.value:
        next_state["is_loading"] = True

    elif type_ == UIActionType.LOADING_FINISHED.value:
        next_state["is_loading"] = False

    elif type_ == UIActionType.ERROR_OCCURRED.value:
        next_state["last_error"] = payload["message"]
        next_state["is_loading"] = False

    # --- System ---
    elif type_ == UIActionType.SYSTEM_STATUS_UPDATED.value:
        current_status = next_state.get("system_status", {})
        new_status = current_status.copy()
        new_status["mssql"] = payload.get("mssql", new_status.get("mssql"))
        new_status["sqlite"] = payload.get("sqlite", new_status.get("sqlite"))
        next_state["system_status"] = new_status

        if payload.get("message"):
            next_state["last_log_message"] = payload["message"]

    return next_state
