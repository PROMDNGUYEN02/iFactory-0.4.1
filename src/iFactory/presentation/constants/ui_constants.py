"""
Presentation: UI Metrics and Theme configuration.
"""

from typing import Final
from src.iFactory.domain.enums.device_status import DeviceStatus


class UIConstants:
    MENU_EXPANDED_WIDTH: Final[int] = 250
    MENU_COLLAPSED_WIDTH: Final[int] = 60
    DEFAULT_FONT_SIZE: Final[int] = 12


class StatusColors:
    LIGHT_THEME: Final[dict[DeviceStatus, str]] = {
        DeviceStatus.RUNNING: "#4CAF50",
        DeviceStatus.SHUTDOWN: "#BDBDBD",
        DeviceStatus.STOP: "#F44336",
        DeviceStatus.MAINTENANCE: "#03A9F4",
        DeviceStatus.ALARM: "#FFEB3B",
        DeviceStatus.UNKNOWN: "#9E9E9E",
    }

    DARK_THEME: Final[dict[DeviceStatus, str]] = {
        DeviceStatus.RUNNING: "#66BB6A",
        DeviceStatus.STOP: "#EF5350",
        # ... các màu dark theme
    }


def get_ui_color(status: DeviceStatus, is_dark_mode: bool = False) -> str:
    palette = StatusColors.DARK_THEME if is_dark_mode else StatusColors.LIGHT_THEME
    return palette.get(status, "#9E9E9E")
