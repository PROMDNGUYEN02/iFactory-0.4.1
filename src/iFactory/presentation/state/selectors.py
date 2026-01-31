# File: presentation/state/selectors.py
from typing import Any, Dict, List, Optional


def select_theme(state: Dict[str, Any]) -> str:
    return state.get("theme", "light")


def select_current_page(state: Dict[str, Any]) -> str:
    return state.get("current_page", "dashboard_page")


def select_devices(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("devices", {})


def select_gantt_data(state: Dict[str, Any]) -> Dict[str, List[Any]]:
    return state.get("gantt_data", {})


def select_selected_device_id(state: Dict[str, Any]) -> Optional[str]:
    return state.get("selected_device_id")


def select_selected_device(state: Dict[str, Any]) -> Optional[Any]:
    device_id = select_selected_device_id(state)
    if not device_id:
        return None
    devices = select_devices(state)
    return devices.get(device_id)


def select_is_loading(state: Dict[str, Any]) -> bool:
    return state.get("is_loading", False)


def select_error(state: Dict[str, Any]) -> Optional[str]:
    return state.get("error")


def select_sidebar_expanded(state: Dict[str, Any]) -> bool:
    return state.get("sidebar_expanded", False)


def select_right_panel_expanded(state: Dict[str, Any]) -> bool:
    return state.get("right_panel_expanded", False)


def select_data_range_days(state: Dict[str, Any]) -> int:
    return state.get("data_range_days", 1)


def select_system_status(state: Dict[str, Any]) -> Dict[str, Any]:
    return state.get("system_status", {"mssql": False, "sqlite": False, "message": ""})


def select_factory_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    devices = select_devices(state)
    if not devices:
        return {"total_output": 0, "total_input": 0, "yield_rate": 0.0, "device_count": 0}

    total_input = 0
    total_output = 0

    for device in devices.values():
        if hasattr(device, "input_count"):
            total_input += device.input_count or 0
            total_output += device.output_count or 0
        elif isinstance(device, dict):
            total_input += device.get("input_count", 0) or 0
            total_output += device.get("output_count", 0) or 0

    yield_rate = (total_output / total_input * 100) if total_input > 0 else 0.0

    return {
        "total_output": total_output,
        "total_input": total_input,
        "yield_rate": round(yield_rate, 2),
        "device_count": len(devices),
    }


__all__ = [
    "select_theme",
    "select_current_page",
    "select_devices",
    "select_gantt_data",
    "select_selected_device_id",
    "select_selected_device",
    "select_is_loading",
    "select_error",
    "select_sidebar_expanded",
    "select_right_panel_expanded",
    "select_data_range_days",
    "select_system_status",
    "select_factory_summary",
]
