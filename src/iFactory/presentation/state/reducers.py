# File: presentation/state/reducers.py
from typing import Any, Dict

from .actions import Action, ActionType

INITIAL_STATE: Dict[str, Any] = {
    "theme": "light",
    "current_page": "dashboard_page",
    "sidebar_expanded": False,
    "right_panel_expanded": False,
    "selected_device_id": None,
    "selected_device_gantt": None,
    "data_range_days": 1,
    "is_loading": False,
    "error": None,
    "devices": {},
    "gantt_data": {},
    "system_status": {
        "mssql": False,
        "sqlite": False,
        "message": "Initializing...",
    },
}


def root_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    if state is None:
        return INITIAL_STATE.copy()

    if not isinstance(action, Action):
        return state

    handlers = {
        ActionType.SET_THEME: _handle_set_theme,
        ActionType.SET_PAGE: _handle_set_page,
        ActionType.TOGGLE_SIDEBAR: _handle_toggle_sidebar,
        ActionType.TOGGLE_RIGHT_PANEL: _handle_toggle_right_panel,
        ActionType.SELECT_DEVICE: _handle_select_device,
        ActionType.DESELECT_DEVICE: _handle_deselect_device,
        ActionType.SET_DATA_RANGE: _handle_set_data_range,
        ActionType.SET_LOADING: _handle_set_loading,
        ActionType.SET_ERROR: _handle_set_error,
        ActionType.CLEAR_ERROR: _handle_clear_error,
        ActionType.LOAD_DEVICES: _handle_load_devices,
        ActionType.LOAD_GANTT: _handle_load_gantt,
        ActionType.SET_SELECTED_DEVICE_GANTT: _handle_set_selected_device_gantt,
        ActionType.UPDATE_SYSTEM_STATUS: _handle_update_system_status,
    }

    handler = handlers.get(action.type)
    if handler:
        return handler(state, action.payload)

    return state


def _handle_set_theme(state: Dict[str, Any], payload: str) -> Dict[str, Any]:
    if payload not in ("light", "dark"):
        return state
    return {**state, "theme": payload}


def _handle_set_page(state: Dict[str, Any], payload: str) -> Dict[str, Any]:
    return {**state, "current_page": payload}


def _handle_toggle_sidebar(state: Dict[str, Any], _: Any) -> Dict[str, Any]:
    return {**state, "sidebar_expanded": not state["sidebar_expanded"]}


def _handle_toggle_right_panel(state: Dict[str, Any], _: Any) -> Dict[str, Any]:
    return {**state, "right_panel_expanded": not state["right_panel_expanded"]}


def _handle_select_device(state: Dict[str, Any], payload: str) -> Dict[str, Any]:
    new_state = {
        **state,
        "selected_device_id": payload,
        "right_panel_expanded": True,
    }
    # Clear gantt when device changes
    if payload != state.get("selected_device_id"):
        new_state["selected_device_gantt"] = None
    return new_state


def _handle_deselect_device(state: Dict[str, Any], _: Any) -> Dict[str, Any]:
    return {
        **state,
        "selected_device_id": None,
        "selected_device_gantt": None,
    }


def _handle_set_data_range(state: Dict[str, Any], payload: int) -> Dict[str, Any]:
    return {**state, "data_range_days": max(1, min(payload, 30))}


def _handle_set_loading(state: Dict[str, Any], payload: bool) -> Dict[str, Any]:
    return {**state, "is_loading": payload}


def _handle_set_error(state: Dict[str, Any], payload: str) -> Dict[str, Any]:
    return {**state, "error": payload, "is_loading": False}


def _handle_clear_error(state: Dict[str, Any], _: Any) -> Dict[str, Any]:
    return {**state, "error": None}


def _handle_load_devices(state: Dict[str, Any], payload: Dict) -> Dict[str, Any]:
    return {**state, "devices": payload, "is_loading": False}


def _handle_load_gantt(state: Dict[str, Any], payload: Dict) -> Dict[str, Any]:
    return {**state, "gantt_data": payload}


def _handle_set_selected_device_gantt(state: Dict[str, Any], payload: Any) -> Dict[str, Any]:
    return {**state, "selected_device_gantt": payload}


def _handle_update_system_status(state: Dict[str, Any], payload: Dict) -> Dict[str, Any]:
    current = state.get("system_status", {})
    updated = {
        "mssql": payload.get("mssql", current.get("mssql", False)),
        "sqlite": payload.get("sqlite", current.get("sqlite", False)),
        "message": payload.get("message") or current.get("message", ""),
    }
    return {**state, "system_status": updated}


__all__ = ["INITIAL_STATE", "root_reducer"]
