# File: presentation/state/selectors.py
from typing import Any, Dict, List, Optional


def select_theme(state: Dict[str, Any]) -> str:
    """Select current theme (light/dark)."""
    return state.get("theme", "light")


def select_current_page(state: Dict[str, Any]) -> str:
    """Select current active page."""
    return state.get("current_page", "dashboard_page")


def select_devices(state: Dict[str, Any]) -> Dict[str, Any]:
    """Select all devices data."""
    return state.get("devices", {})


def select_gantt_data(state: Dict[str, Any]) -> Dict[str, List[Any]]:
    """Select gantt timeline data for all devices."""
    return state.get("gantt_data", {})


def select_selected_device_id(state: Dict[str, Any]) -> Optional[str]:
    """Select the ID of the currently selected device."""
    return state.get("selected_device_id")


def select_selected_device(state: Dict[str, Any]) -> Optional[Any]:
    """Select the full device data for the currently selected device."""
    device_id = select_selected_device_id(state)
    if not device_id:
        return None
    devices = select_devices(state)
    return devices.get(device_id)


def select_selected_device_gantt(state: Dict[str, Any]) -> Optional[Any]:
    """Select the Gantt chart ViewModel for the selected device."""
    return state.get("selected_device_gantt")


def select_selected_device_gantt_segments(state: Dict[str, Any]) -> List[Any]:
    """Select gantt segments for the currently selected device."""
    device_id = select_selected_device_id(state)
    if not device_id:
        return []
    gantt_data = select_gantt_data(state)
    return gantt_data.get(device_id, [])


def select_is_loading(state: Dict[str, Any]) -> bool:
    """Select loading state."""
    return state.get("is_loading", False)


def select_error(state: Dict[str, Any]) -> Optional[str]:
    """Select current error message."""
    return state.get("error")


def select_sidebar_expanded(state: Dict[str, Any]) -> bool:
    """Select sidebar expansion state."""
    return state.get("sidebar_expanded", False)


def select_right_panel_expanded(state: Dict[str, Any]) -> bool:
    """Select right panel expansion state."""
    return state.get("right_panel_expanded", False)


def select_data_range_days(state: Dict[str, Any]) -> int:
    """Select current data range in days."""
    return state.get("data_range_days", 1)


def select_system_status(state: Dict[str, Any]) -> Dict[str, Any]:
    """Select system connection status."""
    return state.get("system_status", {"mssql": False, "sqlite": False, "message": ""})


def select_factory_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate and select factory summary statistics."""
    devices = select_devices(state)
    if not devices:
        return {
            "total_output": 0,
            "total_input": 0,
            "yield_rate": 0.0,
            "device_count": 0,
            "running_count": 0,
            "stopped_count": 0,
            "alarm_count": 0,
        }

    total_input = 0
    total_output = 0
    running_count = 0
    stopped_count = 0
    alarm_count = 0

    for device in devices.values():
        # Get values from dict or object
        if isinstance(device, dict):
            total_input += device.get("input_count", 0) or 0
            total_output += device.get("output_count", 0) or 0
            status_code = device.get("status_code", 0)
        else:
            total_input += getattr(device, "input_count", 0) or 0
            total_output += getattr(device, "output_count", 0) or 0
            status_code = getattr(device, "status_code", 0)

        # Count by status
        if status_code == 1:
            running_count += 1
        elif status_code == 3:
            stopped_count += 1
        elif status_code == 5:
            alarm_count += 1

    yield_rate = (total_output / total_input * 100) if total_input > 0 else 0.0

    return {
        "total_output": total_output,
        "total_input": total_input,
        "yield_rate": round(yield_rate, 2),
        "device_count": len(devices),
        "running_count": running_count,
        "stopped_count": stopped_count,
        "alarm_count": alarm_count,
    }


def select_device_by_id(state: Dict[str, Any], device_id: str) -> Optional[Any]:
    """Select a specific device by ID."""
    devices = select_devices(state)
    return devices.get(device_id)


def select_device_gantt_by_id(state: Dict[str, Any], device_id: str) -> List[Any]:
    """Select gantt segments for a specific device by ID."""
    gantt_data = select_gantt_data(state)
    return gantt_data.get(device_id, [])


__all__ = [
    "select_theme",
    "select_current_page",
    "select_devices",
    "select_gantt_data",
    "select_selected_device_id",
    "select_selected_device",
    "select_selected_device_gantt",
    "select_selected_device_gantt_segments",
    "select_is_loading",
    "select_error",
    "select_sidebar_expanded",
    "select_right_panel_expanded",
    "select_data_range_days",
    "select_system_status",
    "select_factory_summary",
    "select_device_by_id",
    "select_device_gantt_by_id",
]
