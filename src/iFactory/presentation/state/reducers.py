# src/iFactory/presentation/state/reducers.py
"""
Composable Reducer System.

Features:
- Pure functions for state transitions
- Strongly typed with AppState
- Composable sub-reducers
- Backward compatible dict output
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from .types import (
    AppState,
    DeviceSnapshot,
    GanttSegment,
    PageId,
    SelectionState,
    SystemStatus,
    ThemeMode,
    UIState,
)
from .actions import (
    Action,
    ActionType,
    LoadDevicesPayload,
    LoadGanttPayload,
    SelectDevicePayload,
    SetDataRangePayload,
    SetErrorPayload,
    SetPageDevicesPayload,
    SetPagePayload,
    SetThemePayload,
    SyncCompletedPayload,
    SyncFailedPayload,
    SystemStatusPayload,
    UpdateDevicePayload,
)

S = TypeVar("S")

# Type alias for reducer function
Reducer = Callable[[S, Action], S]


# ============================================================================
# Initial State
# ============================================================================


def create_initial_state() -> AppState:
    """Create fresh initial state."""
    return AppState()


INITIAL_STATE = create_initial_state()


# ============================================================================
# Sub-Reducers
# ============================================================================


def theme_reducer(state: AppState, action: Action) -> AppState:
    """Handle theme-related actions."""
    if action.type == ActionType.SET_THEME:
        payload = action.payload
        if isinstance(payload, SetThemePayload):
            theme = ThemeMode.from_string(payload.theme)
        elif isinstance(payload, str):
            theme = ThemeMode.from_string(payload)
        else:
            return state
        return state.with_theme(theme)

    if action.type == ActionType.TOGGLE_THEME:
        new_theme = ThemeMode.DARK if state.theme == ThemeMode.LIGHT else ThemeMode.LIGHT
        return state.with_theme(new_theme)

    return state


def navigation_reducer(state: AppState, action: Action) -> AppState:
    """Handle navigation actions."""
    if action.type == ActionType.SET_PAGE:
        payload = action.payload
        if isinstance(payload, SetPagePayload):
            page = PageId.from_string(payload.page)
        elif isinstance(payload, str):
            page = PageId.from_string(payload)
        else:
            return state
        return state.with_page(page)

    return state


def ui_reducer(state: AppState, action: Action) -> AppState:
    """Handle UI state actions."""
    ui = state.ui

    if action.type == ActionType.TOGGLE_SIDEBAR:
        new_ui = UIState(
            sidebar_expanded=not ui.sidebar_expanded,
            right_panel_expanded=ui.right_panel_expanded,
            is_loading=ui.is_loading,
            error_message=ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.SET_SIDEBAR:
        expanded = bool(action.payload)
        if ui.sidebar_expanded == expanded:
            return state
        new_ui = UIState(
            sidebar_expanded=expanded,
            right_panel_expanded=ui.right_panel_expanded,
            is_loading=ui.is_loading,
            error_message=ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.TOGGLE_RIGHT_PANEL:
        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=not ui.right_panel_expanded,
            is_loading=ui.is_loading,
            error_message=ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.SET_RIGHT_PANEL:
        expanded = bool(action.payload)
        if ui.right_panel_expanded == expanded:
            return state
        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=expanded,
            is_loading=ui.is_loading,
            error_message=ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.SET_LOADING:
        is_loading = bool(action.payload)
        if ui.is_loading == is_loading:
            return state
        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=ui.right_panel_expanded,
            is_loading=is_loading,
            error_message=ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.SET_ERROR:
        payload = action.payload
        if isinstance(payload, SetErrorPayload):
            message = payload.message
        elif isinstance(payload, str):
            message = payload
        else:
            message = str(payload) if payload else None

        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=ui.right_panel_expanded,
            is_loading=False,  # Clear loading on error
            error_message=message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.CLEAR_ERROR:
        if ui.error_message is None:
            return state
        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=ui.right_panel_expanded,
            is_loading=ui.is_loading,
            error_message=None,
        )
        return state.with_ui(new_ui)

    return state


def selection_reducer(state: AppState, action: Action) -> AppState:
    """Handle selection actions."""
    selection = state.selection
    ui = state.ui

    if action.type == ActionType.SELECT_DEVICE:
        payload = action.payload
        if isinstance(payload, SelectDevicePayload):
            device_id = payload.device_id
            open_panel = payload.open_panel
        elif isinstance(payload, str):
            device_id = payload
            open_panel = True
        else:
            return state

        # Update selection
        new_selection = SelectionState(
            selected_device_id=device_id,
            selected_gantt=None if device_id != selection.selected_device_id else selection.selected_gantt,
        )

        # Also open right panel
        new_ui = UIState(
            sidebar_expanded=ui.sidebar_expanded,
            right_panel_expanded=True,
            is_loading=ui.is_loading,
            error_message=ui.error_message,
        )

        return state.with_selection(new_selection).with_ui(new_ui)

    if action.type == ActionType.SELECT_DEVICE_ONLY:
        payload = action.payload
        if isinstance(payload, SelectDevicePayload):
            device_id = payload.device_id
        elif isinstance(payload, str):
            device_id = payload
        else:
            return state

        new_selection = SelectionState(
            selected_device_id=device_id,
            selected_gantt=None if device_id != selection.selected_device_id else selection.selected_gantt,
        )
        return state.with_selection(new_selection)

    if action.type == ActionType.DESELECT_DEVICE:
        if not selection.has_selection:
            return state
        new_selection = SelectionState()
        return state.with_selection(new_selection)

    if action.type == ActionType.SET_DEVICE_GANTT:
        new_selection = SelectionState(
            selected_device_id=selection.selected_device_id,
            selected_gantt=action.payload,
        )
        return state.with_selection(new_selection)

    return state


def devices_reducer(state: AppState, action: Action) -> AppState:
    """Handle device data actions."""
    if action.type == ActionType.LOAD_DEVICES:
        payload = action.payload

        if isinstance(payload, LoadDevicesPayload):
            devices = payload.devices
        elif isinstance(payload, dict):
            # Backward compatibility
            devices = tuple(DeviceSnapshot.from_dict({**v, "device_id": k}) if isinstance(v, dict) else v for k, v in payload.items())
        elif isinstance(payload, (list, tuple)):
            devices = tuple(payload)
        else:
            return state

        # Update UI to clear loading
        new_ui = UIState(
            sidebar_expanded=state.ui.sidebar_expanded,
            right_panel_expanded=state.ui.right_panel_expanded,
            is_loading=False,
            error_message=state.ui.error_message,
        )

        return state.with_devices(devices).with_ui(new_ui)

    if action.type == ActionType.UPDATE_DEVICES:
        payload = action.payload
        if not isinstance(payload, dict):
            return state

        # Convert existing devices to dict for merging
        current = {d.device_id: d for d in state.devices}

        # Merge updates
        for device_id, data in payload.items():
            if isinstance(data, DeviceSnapshot):
                current[device_id] = data
            elif isinstance(data, dict):
                current[device_id] = DeviceSnapshot.from_dict({**data, "device_id": device_id})

        return state.with_devices(tuple(current.values()))

    if action.type == ActionType.UPDATE_DEVICE:
        payload = action.payload
        if not isinstance(payload, UpdateDevicePayload):
            return state

        # Find and update the specific device
        new_devices = []
        found = False
        for device in state.devices:
            if device.device_id == payload.device_id:
                # Create updated device
                updates = payload.updates
                new_device = DeviceSnapshot(
                    device_id=device.device_id,
                    equipment_code=updates.get("equipment_code", device.equipment_code),
                    status_code=updates.get("status_code", device.status_code),
                    status_name=updates.get("status_name", device.status_name),
                    input_count=updates.get("input_count", device.input_count),
                    output_count=updates.get("output_count", device.output_count),
                    ng_count=updates.get("ng_count", device.ng_count),
                    current_model=updates.get("current_model", device.current_model),
                    current_lot=updates.get("current_lot", device.current_lot),
                    last_update=updates.get("last_update", datetime.now()),
                )
                new_devices.append(new_device)
                found = True
            else:
                new_devices.append(device)

        if not found:
            return state

        return state.with_devices(tuple(new_devices))

    return state


def gantt_reducer(state: AppState, action: Action) -> AppState:
    """Handle Gantt data actions."""
    if action.type == ActionType.LOAD_GANTT:
        payload = action.payload

        if isinstance(payload, LoadGanttPayload):
            device_id = payload.device_id
            segments = payload.segments
        elif isinstance(payload, dict):
            # Handle legacy dict format {device_id: [segments]}
            # Just take first entry
            for device_id, segs in payload.items():
                segments = tuple(
                    (
                        GanttSegment(
                            start_time=s.get("start_time") or s.start_time,
                            end_time=s.get("end_time") or s.end_time,
                            status_code=s.get("status_code") or s.status_code,
                            status_name=s.get("status_name", ""),
                        )
                        if isinstance(s, dict)
                        else s
                    )
                    for s in segs
                )
                break
            else:
                return state
        else:
            return state

        # Update gantt_data
        new_gantt = list(state.gantt_data)
        updated = False
        for i, (dev_id, _) in enumerate(new_gantt):
            if dev_id == device_id:
                new_gantt[i] = (device_id, segments)
                updated = True
                break

        if not updated:
            new_gantt.append((device_id, segments))

        # Create new state with updated gantt
        return AppState(
            theme=state.theme,
            current_page=state.current_page,
            ui=state.ui,
            selection=state.selection,
            devices=state.devices,
            gantt_data=tuple(new_gantt),
            page_devices=state.page_devices,
            data_range_days=state.data_range_days,
            system_status=state.system_status,
            last_sync=state.last_sync,
        )

    return state


def settings_reducer(state: AppState, action: Action) -> AppState:
    """Handle settings actions."""
    if action.type == ActionType.SET_DATA_RANGE:
        payload = action.payload

        if isinstance(payload, SetDataRangePayload):
            days = payload.days
        elif isinstance(payload, int):
            days = max(1, min(payload, 30))
        else:
            return state

        if state.data_range_days == days:
            return state

        return AppState(
            theme=state.theme,
            current_page=state.current_page,
            ui=state.ui,
            selection=state.selection,
            devices=state.devices,
            gantt_data=state.gantt_data,
            page_devices=state.page_devices,
            data_range_days=days,
            system_status=state.system_status,
            last_sync=state.last_sync,
        )

    if action.type == ActionType.SET_PAGE_DEVICES:
        payload = action.payload

        if isinstance(payload, SetPageDevicesPayload):
            page = payload.page
            device_ids = payload.device_ids
        elif isinstance(payload, dict):
            page = payload.get("page", "")
            device_ids = tuple(payload.get("devices", []))
        else:
            return state

        # Update page_devices
        new_page_devices = list(state.page_devices)
        updated = False
        for i, (p, _) in enumerate(new_page_devices):
            if p == page:
                new_page_devices[i] = (page, device_ids)
                updated = True
                break

        if not updated:
            new_page_devices.append((page, device_ids))

        return AppState(
            theme=state.theme,
            current_page=state.current_page,
            ui=state.ui,
            selection=state.selection,
            devices=state.devices,
            gantt_data=state.gantt_data,
            page_devices=tuple(new_page_devices),
            data_range_days=state.data_range_days,
            system_status=state.system_status,
            last_sync=state.last_sync,
        )

    return state


def system_reducer(state: AppState, action: Action) -> AppState:
    """Handle system status actions."""
    if action.type == ActionType.UPDATE_SYSTEM_STATUS:
        payload = action.payload

        if isinstance(payload, SystemStatusPayload):
            new_status = SystemStatus(
                mssql_connected=payload.mssql_connected,
                sqlite_connected=payload.sqlite_connected,
                message=payload.message,
                last_check=datetime.now(),
            )
        elif isinstance(payload, dict):
            new_status = SystemStatus(
                mssql_connected=payload.get("mssql", False),
                sqlite_connected=payload.get("sqlite", False),
                message=payload.get("message", ""),
                last_check=datetime.now(),
            )
        else:
            return state

        return AppState(
            theme=state.theme,
            current_page=state.current_page,
            ui=state.ui,
            selection=state.selection,
            devices=state.devices,
            gantt_data=state.gantt_data,
            page_devices=state.page_devices,
            data_range_days=state.data_range_days,
            system_status=new_status,
            last_sync=state.last_sync,
        )

    if action.type == ActionType.SYNC_STARTED:
        new_ui = UIState(
            sidebar_expanded=state.ui.sidebar_expanded,
            right_panel_expanded=state.ui.right_panel_expanded,
            is_loading=True,
            error_message=state.ui.error_message,
        )
        return state.with_ui(new_ui)

    if action.type == ActionType.SYNC_COMPLETED:
        payload = action.payload

        if isinstance(payload, SyncCompletedPayload):
            sync_time = payload.timestamp
        elif isinstance(payload, dict):
            sync_time = payload.get("timestamp", datetime.now())
        else:
            sync_time = datetime.now()

        new_ui = UIState(
            sidebar_expanded=state.ui.sidebar_expanded,
            right_panel_expanded=state.ui.right_panel_expanded,
            is_loading=False,
            error_message=None,
        )

        return AppState(
            theme=state.theme,
            current_page=state.current_page,
            ui=new_ui,
            selection=state.selection,
            devices=state.devices,
            gantt_data=state.gantt_data,
            page_devices=state.page_devices,
            data_range_days=state.data_range_days,
            system_status=state.system_status,
            last_sync=sync_time,
        )

    if action.type == ActionType.SYNC_FAILED:
        payload = action.payload

        if isinstance(payload, SyncFailedPayload):
            error_msg = payload.error_message
        elif isinstance(payload, str):
            error_msg = payload
        else:
            error_msg = "Sync failed"

        new_ui = UIState(
            sidebar_expanded=state.ui.sidebar_expanded,
            right_panel_expanded=state.ui.right_panel_expanded,
            is_loading=False,
            error_message=error_msg,
        )

        return state.with_ui(new_ui)

    return state


# ============================================================================
# Root Reducer
# ============================================================================


def combine_reducers(*reducers: Reducer[AppState]) -> Reducer[AppState]:
    """
    Combine multiple reducers into a single reducer.

    Each reducer is called in sequence, passing the state through.
    """

    def combined(state: AppState, action: Action) -> AppState:
        for reducer in reducers:
            state = reducer(state, action)
        return state

    return combined


# Combined root reducer
root_reducer = combine_reducers(
    theme_reducer,
    navigation_reducer,
    ui_reducer,
    selection_reducer,
    devices_reducer,
    gantt_reducer,
    settings_reducer,
    system_reducer,
)


# ============================================================================
# Backward Compatibility - Dict-based reducer
# ============================================================================


def root_reducer_dict(state: Optional[Dict[str, Any]], action: Action) -> Dict[str, Any]:
    """
    Backward compatible reducer that works with dict state.

    Converts between dict and AppState internally.
    """
    if state is None:
        return INITIAL_STATE.to_dict()

    # This is for backward compatibility only
    # New code should use AppState directly

    # For now, delegate to the old implementation
    # In production, you'd convert dict -> AppState -> process -> dict
    return _legacy_root_reducer(state, action)


def _legacy_root_reducer(state: Dict[str, Any], action: Action) -> Dict[str, Any]:
    """Legacy dict-based reducer for backward compatibility."""
    if not isinstance(action, Action):
        return state

    # Handle each action type with dict operations
    # (This maintains backward compatibility while we migrate)

    handlers = {
        ActionType.SET_THEME: _dict_handle_set_theme,
        ActionType.TOGGLE_THEME: _dict_handle_toggle_theme,
        ActionType.SET_PAGE: _dict_handle_set_page,
        ActionType.TOGGLE_SIDEBAR: _dict_handle_toggle_sidebar,
        ActionType.SET_SIDEBAR: _dict_handle_set_sidebar,
        ActionType.TOGGLE_RIGHT_PANEL: _dict_handle_toggle_right_panel,
        ActionType.SET_RIGHT_PANEL: _dict_handle_set_right_panel,
        ActionType.SELECT_DEVICE: _dict_handle_select_device,
        ActionType.SELECT_DEVICE_ONLY: _dict_handle_select_device_only,
        ActionType.DESELECT_DEVICE: _dict_handle_deselect_device,
        ActionType.SET_LOADING: _dict_handle_set_loading,
        ActionType.SET_ERROR: _dict_handle_set_error,
        ActionType.CLEAR_ERROR: _dict_handle_clear_error,
        ActionType.LOAD_DEVICES: _dict_handle_load_devices,
        ActionType.UPDATE_DEVICES: _dict_handle_update_devices,
        ActionType.SET_DATA_RANGE: _dict_handle_set_data_range,
        ActionType.UPDATE_SYSTEM_STATUS: _dict_handle_update_system_status,
        ActionType.SYNC_COMPLETED: _dict_handle_sync_completed,
        ActionType.SET_PAGE_DEVICES: _dict_handle_set_page_devices,
        ActionType.SET_DEVICE_GANTT: _dict_handle_set_device_gantt,
    }

    handler = handlers.get(action.type)
    if handler:
        return handler(state, action.payload)

    return state


# Legacy dict handlers (keeping existing logic)
def _dict_handle_set_theme(state: Dict, payload) -> Dict:
    theme = payload.theme if hasattr(payload, "theme") else payload
    if theme not in ("light", "dark"):
        return state
    return {**state, "theme": theme}


def _dict_handle_toggle_theme(state: Dict, payload) -> Dict:
    current = state.get("theme", "light")
    new_theme = "dark" if current == "light" else "light"
    return {**state, "theme": new_theme}


def _dict_handle_set_page(state: Dict, payload) -> Dict:
    page = payload.page if hasattr(payload, "page") else payload
    normalized = page.replace("daboard", "electrode")
    return {**state, "current_page": normalized}


def _dict_handle_toggle_sidebar(state: Dict, _) -> Dict:
    return {**state, "sidebar_expanded": not state.get("sidebar_expanded", False)}


def _dict_handle_set_sidebar(state: Dict, payload) -> Dict:
    return {**state, "sidebar_expanded": bool(payload)}


def _dict_handle_toggle_right_panel(state: Dict, _) -> Dict:
    return {**state, "right_panel_expanded": not state.get("right_panel_expanded", False)}


def _dict_handle_set_right_panel(state: Dict, payload) -> Dict:
    return {**state, "right_panel_expanded": bool(payload)}


def _dict_handle_select_device(state: Dict, payload) -> Dict:
    device_id = payload.device_id if hasattr(payload, "device_id") else payload
    new_state = {
        **state,
        "selected_device_id": device_id,
        "right_panel_expanded": True,
    }
    if device_id != state.get("selected_device_id"):
        new_state["selected_device_gantt"] = None
    return new_state


def _dict_handle_select_device_only(state: Dict, payload) -> Dict:
    device_id = payload.device_id if hasattr(payload, "device_id") else payload
    new_state = {**state, "selected_device_id": device_id}
    if device_id != state.get("selected_device_id"):
        new_state["selected_device_gantt"] = None
    return new_state


def _dict_handle_deselect_device(state: Dict, _) -> Dict:
    return {**state, "selected_device_id": None, "selected_device_gantt": None}


def _dict_handle_set_loading(state: Dict, payload) -> Dict:
    return {**state, "is_loading": bool(payload)}


def _dict_handle_set_error(state: Dict, payload) -> Dict:
    msg = payload.message if hasattr(payload, "message") else payload
    return {**state, "error": msg, "is_loading": False}


def _dict_handle_clear_error(state: Dict, _) -> Dict:
    return {**state, "error": None}


def _dict_handle_load_devices(state: Dict, payload) -> Dict:
    if hasattr(payload, "devices"):
        # Typed payload
        devices = {d.device_id: d.to_dict() for d in payload.devices}
    elif isinstance(payload, dict):
        devices = payload
    else:
        return state
    return {**state, "devices": devices, "is_loading": False}


def _dict_handle_update_devices(state: Dict, payload) -> Dict:
    current = dict(state.get("devices", {}))
    if isinstance(payload, dict):
        current.update(payload)
    return {**state, "devices": current, "is_loading": False}


def _dict_handle_set_data_range(state: Dict, payload) -> Dict:
    days = payload.days if hasattr(payload, "days") else payload
    return {**state, "data_range_days": max(1, min(int(days), 30))}


def _dict_handle_update_system_status(state: Dict, payload) -> Dict:
    current = state.get("system_status", {})
    if hasattr(payload, "mssql_connected"):
        updated = {
            "mssql": payload.mssql_connected,
            "sqlite": payload.sqlite_connected,
            "message": payload.message or current.get("message", ""),
        }
    elif isinstance(payload, dict):
        updated = {
            "mssql": payload.get("mssql", current.get("mssql", False)),
            "sqlite": payload.get("sqlite", current.get("sqlite", False)),
            "message": payload.get("message") or current.get("message", ""),
        }
    else:
        return state
    return {**state, "system_status": updated}


def _dict_handle_sync_completed(state: Dict, payload) -> Dict:
    if hasattr(payload, "timestamp"):
        ts = payload.timestamp
    elif isinstance(payload, dict):
        ts = payload.get("timestamp", datetime.now())
    else:
        ts = datetime.now()
    return {**state, "last_sync": ts, "is_loading": False}


def _dict_handle_set_page_devices(state: Dict, payload) -> Dict:
    if hasattr(payload, "page"):
        page, devices = payload.page, list(payload.device_ids)
    elif isinstance(payload, dict):
        page = payload.get("page", "")
        devices = payload.get("devices", [])
    else:
        return state
    page_devices = dict(state.get("page_devices", {}))
    page_devices[page] = devices
    return {**state, "page_devices": page_devices}


def _dict_handle_set_device_gantt(state: Dict, payload) -> Dict:
    return {**state, "selected_device_gantt": payload}


# For backward compatibility, INITIAL_STATE as dict
INITIAL_STATE_DICT: Dict[str, Any] = {
    "theme": "light",
    "current_page": "electrode_page",
    "sidebar_expanded": False,
    "right_panel_expanded": False,
    "selected_device_id": None,
    "selected_device_gantt": None,
    "data_range_days": 1,
    "is_loading": False,
    "error": None,
    "devices": {},
    "gantt_data": {},
    "page_devices": {},
    "last_sync": None,
    "system_status": {
        "mssql": False,
        "sqlite": False,
        "message": "Initializing...",
    },
}


__all__ = [
    "INITIAL_STATE",
    "INITIAL_STATE_DICT",
    "create_initial_state",
    "root_reducer",
    "root_reducer_dict",
    "combine_reducers",
    # Sub-reducers
    "theme_reducer",
    "navigation_reducer",
    "ui_reducer",
    "selection_reducer",
    "devices_reducer",
    "gantt_reducer",
    "settings_reducer",
    "system_reducer",
]
