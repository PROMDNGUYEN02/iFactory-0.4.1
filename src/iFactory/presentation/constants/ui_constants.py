"""
Presentation: UI Metrics and Theme configuration.
Now uses ThemeManager for centralized color resolution.
"""

from typing import Dict, Final
from ..resources.themes.theme_manager import theme_manager


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
    Status mappings.
    Colors are now retrieved dynamically from ThemeManager.
    """

    UNKNOWN: Final[int] = 0
    RUNNING: Final[int] = 1
    SHUTDOWN: Final[int] = 2
    STOPPED: Final[int] = 3
    MAINTENANCE: Final[int] = 4
    ALARM: Final[int] = 5

    STATUS_NAMES: Final[Dict[int, str]] = {
        0: "Unknown",
        1: "Running",
        2: "Shutdown",
        3: "Stopped",
        4: "Maintenance",
        5: "Alarm",
    }

    # Mapping to keys in variables.json
    _KEYS: Final[Dict[int, str]] = {
        0: "status.unknown",
        1: "status.running",
        2: "status.shutdown",
        3: "status.stopped",
        4: "status.maintenance",
        5: "status.alarm",
    }

    @classmethod
    def get_color(cls, status_code: int) -> str:
        """
        Get dynamic color from ThemeManager based on current app state.
        NO THEME ARGUMENT NEEDED HERE.
        """
        key = cls._KEYS.get(status_code, "status.unknown")
        return theme_manager.get_color(key)

    @classmethod
    def get_name(cls, status_code: int) -> str:
        return cls.STATUS_NAMES.get(status_code, "Unknown")


# Wrapper functions for backward compatibility if needed
def get_ui_color(status_code: int) -> str:
    return StatusColors.get_color(status_code)


def get_status_display_name(status_code: int) -> str:
    return StatusColors.get_name(status_code)
