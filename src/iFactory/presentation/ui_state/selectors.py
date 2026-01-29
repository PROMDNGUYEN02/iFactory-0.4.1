"""Selectors for querying the Redux Store."""

from typing import Any, Dict, Optional


def select_theme(state: Dict[str, Any]) -> str:
    return state.get("theme", "light")


def select_current_page(state: Dict[str, Any]) -> str:
    return state.get("current_page", "daboard_page")


def select_all_devices(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("devices", {})


def select_gantt_timeline(state: Dict[str, Any]) -> Dict[str, list]:
    return state.get("gantt_timeline", {})


def select_is_loading(state: Dict[str, Any]) -> bool:
    return state.get("is_loading", False)


def select_last_error(state: Dict[str, Any]) -> Optional[str]:
    return state.get("last_error")


def select_left_menu_expanded(state: Dict[str, Any]) -> bool:
    return state.get("left_menu_expanded", True)


def select_right_panel_expanded(state: Dict[str, Any]) -> bool:
    return state.get("right_panel_expanded", False)


def select_selected_device_id(state: Dict[str, Any]) -> Optional[str]:
    return state.get("selected_device_id")


def select_data_range_days(state: Dict[str, Any]) -> int:
    return state.get("data_range_days", 1)


def select_factory_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate factory statistics from device data."""
    devices = state.get("devices", {})

    total_in = sum(getattr(d, "input_count", 0) for d in devices.values())
    total_out = sum(getattr(d, "output_count", 0) for d in devices.values())
    total_lost = sum(getattr(d, "error_count", 0) for d in devices.values())

    yield_rate = (total_out / total_in * 100) if total_in > 0 else 0.0

    return {
        "output": total_out,
        "yield_rate": round(yield_rate, 2),
        "lost": total_lost,
    }


def select_selected_device_data(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get detailed data for selected device."""
    selected_id = state.get("selected_device_id")
    if not selected_id:
        return None

    device = state.get("devices", {}).get(selected_id)
    if not device:
        return {
            "id": selected_id,
            "status": "Loading...",
            "color": "#888888",
            "inputs": 0,
            "outputs": 0,
            "error": "...",
            "last_update": None,
        }

    return {
        "id": selected_id,
        "status": getattr(device, "status_display", "Unknown"),
        "color": getattr(device, "status_color", "#888888"),
        "inputs": getattr(device, "input_count", 0),
        "outputs": getattr(device, "output_count", 0),
        "error": getattr(device, "last_error", "None"),
        "oee": getattr(device, "oee", 0),
        "yield_rate": getattr(device, "yield_rate", 0),
        "cycle_time": getattr(device, "cycle_time", 0.0),
        "last_update": getattr(device, "last_update", None),
    }


__all__ = [
    "select_theme",
    "select_current_page",
    "select_all_devices",
    "select_gantt_timeline",
    "select_is_loading",
    "select_last_error",
    "select_left_menu_expanded",
    "select_right_panel_expanded",
    "select_selected_device_id",
    "select_factory_summary",
    "select_selected_device_data",
    "select_data_range_days",
]
