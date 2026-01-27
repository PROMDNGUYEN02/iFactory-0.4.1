"""
Presentation: UI Metrics and Theme configuration.
Pure presentation layer - NO domain imports.
"""

from typing import Dict, Final


class UIConstants:
    """UI dimension and layout constants."""

    MENU_EXPANDED_WIDTH: Final[int] = 240
    MENU_COLLAPSED_WIDTH: Final[int] = 50
    RIGHT_PANEL_WIDTH_EXPANDED: Final[int] = 320
    RIGHT_PANEL_WIDTH_COLLAPSED: Final[int] = 0

    DEFAULT_FONT_SIZE: Final[int] = 12
    ANIMATION_DURATION_MS: Final[int] = 300

    FAST_REFRESH_MS: Final[int] = 3000
    SLOW_REFRESH_MS: Final[int] = 5000


class StatusColors:
    """
    Status color mappings for UI display.
    Uses integer status codes.
    """

    UNKNOWN: Final[int] = 0
    RUNNING: Final[int] = 1
    SHUTDOWN: Final[int] = 2
    STOPPED: Final[int] = 3
    MAINTENANCE: Final[int] = 4
    ALARM: Final[int] = 5

    LIGHT_THEME: Final[Dict[int, str]] = {
        0: "#9E9E9E",
        1: "#4CAF50",
        2: "#BDBDBD",
        3: "#F44336",
        4: "#03A9F4",
        5: "#FFEB3B",
    }

    DARK_THEME: Final[Dict[int, str]] = {
        0: "#757575",
        1: "#66BB6A",
        2: "#9E9E9E",
        3: "#EF5350",
        4: "#29B6F6",
        5: "#FDD835",
    }

    STATUS_NAMES: Final[Dict[int, str]] = {
        0: "Unknown",
        1: "Running",
        2: "Shutdown",
        3: "Stopped",
        4: "Maintenance",
        5: "Alarm",
    }

    @classmethod
    def get_color(cls, status_code: int, theme: str = "light") -> str:
        palette = cls.DARK_THEME if theme == "dark" else cls.LIGHT_THEME
        return palette.get(status_code, "#9E9E9E")

    @classmethod
    def get_name(cls, status_code: int) -> str:
        return cls.STATUS_NAMES.get(status_code, "Unknown")


def get_ui_color(status_code: int, is_dark_mode: bool = False) -> str:
    theme = "dark" if is_dark_mode else "light"
    return StatusColors.get_color(status_code, theme)


def get_status_display_name(status_code: int) -> str:
    return StatusColors.get_name(status_code)
