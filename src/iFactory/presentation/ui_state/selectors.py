"""
Selectors for querying the Redux Store.
ĐÃ CHUYỂN SANG CHẾ ĐỘ DỮ LIỆU THẬT 100% (REAL DATA).
"""

from typing import Dict, Any


def select_theme(state: Dict[str, Any]) -> str:
    return state.get("theme", "light")


def select_current_page(state: Dict[str, Any]) -> str:
    return state.get("current_page", "daboard_page")


def select_all_devices(state: Dict[str, Any]) -> Dict[str, Any]:
    # Trả về nguyên gốc danh sách thiết bị thật từ Database
    return state.get("devices", {})


def select_factory_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """Tính toán thống kê TỔNG thực tế của cả nhà máy."""
    devices = state.get("devices", {})

    # 1. Tính tổng thực tế từ tất cả các máy (Nếu chưa có dữ liệu thì = 0)
    total_in = sum(getattr(d, "input_count", 0) for d in devices.values())
    total_out = sum(getattr(d, "output_count", 0) for d in devices.values())
    total_lost = sum(getattr(d, "error_count", 0) for d in devices.values())

    # 2. Tính hiệu suất thật (Yield Rate) theo công thức: (Output / Input) * 100
    yield_rate = 0.0
    if total_in > 0:
        yield_rate = (total_out / total_in) * 100

    return {"output": total_out, "yield_rate": round(yield_rate, 2), "lost": total_lost}  # Làm tròn 2 chữ số thập phân


def select_gantt_timeline(state: Dict[str, Any]) -> Dict[str, list]:
    """Lấy dữ liệu Lịch sử (Timeline) THẬT của từng máy."""
    devices = state.get("devices", {})
    timeline = {}

    for code, dev in devices.items():
        # Lấy thuộc tính timeline thật từ DeviceViewModel (do BackgroundWorker đổ về)
        # Nếu máy chưa có lịch sử, trả về list rỗng [] để biểu đồ trống.
        timeline[code] = getattr(dev, "timeline", [])

    return timeline


def select_selected_device_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """Lấy dữ liệu THẬT của máy đang được người dùng Click."""
    selected_id = state.get("selected_device_id")
    if not selected_id:
        return None

    device = state.get("devices", {}).get(selected_id)

    # TRƯỜNG HỢP: Database chưa load xong dữ liệu máy này
    if not device:
        return {"id": selected_id, "status": "Loading DB...", "color": "#888888", "inputs": 0, "outputs": 0, "error": "..."}

    # TRƯỜNG HỢP: Đã có dữ liệu từ Database -> Lấy giá trị thật
    return {
        "id": selected_id,
        "status": getattr(device, "status_label", "Unknown"),
        "color": getattr(device, "status_color", "#888888"),
        "inputs": getattr(device, "input_count", 0),
        "outputs": getattr(device, "output_count", 0),
        "error": getattr(device, "last_error", "None"),
    }


__all__ = [
    "select_theme",
    "select_current_page",
    "select_all_devices",
    "select_factory_summary",
    "select_gantt_timeline",
    "select_selected_device_data",
]
