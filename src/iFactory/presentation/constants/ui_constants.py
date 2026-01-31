"""
UI Constants - Single Source of Truth for Layout, Timing, and Styling.
"""

from typing import Dict, Final


class UIConstants:
    """Global layout dimensions and timing constants."""

    # Navigation & Shell
    MENU_COLLAPSED_WIDTH: Final[int] = 60
    MENU_EXPANDED_WIDTH: Final[int] = 200
    RIGHT_PANEL_WIDTH_COLLAPSED: Final[int] = 0
    RIGHT_PANEL_WIDTH_EXPANDED: Final[int] = 350

    # Animation Durations (ms)
    ANIMATION_DURATION: Final[int] = 300

    # Polling Intervals (ms)
    POLL_INTERVAL_DEVICE: Final[int] = 3000
    POLL_INTERVAL_GANTT: Final[int] = 10000

    # Legacy alias for backward compatibility
    FAST_REFRESH_MS = POLL_INTERVAL_DEVICE


class StatusColors:
    """
    Centralized Status Color Definitions.
    Ensures consistency between Legend, Canvas, and Gantt charts.
    """

    # Status Codes (Integer Constants)
    # Required for Presenter logic relying on class attributes
    UNKNOWN_CODE: Final[int] = 0
    RUNNING_CODE: Final[int] = 1
    SHUTDOWN_CODE: Final[int] = 2
    STOPPED_CODE: Final[int] = 3
    MAINTENANCE_CODE: Final[int] = 4
    ALARM_CODE: Final[int] = 5

    # Hex Color Codes (Visual Representation)
    UNKNOWN: Final[str] = "#9E9E9E"  # Gray
    RUNNING: Final[str] = "#3bb806"  # Green
    SHUTDOWN: Final[str] = "#555555"  # Dark Gray
    STOPPED: Final[str] = "#FFC107"  # Amber/Yellow (Warning)
    MAINTENANCE: Final[str] = "#38c0bf"  # Cyan/Teal
    ALARM: Final[str] = "#bd1e15"  # Red

    # Aliases for different naming conventions
    IDLE: Final[str] = STOPPED
    TEST: Final[str] = MAINTENANCE
    ERROR: Final[str] = ALARM
    OFFLINE: Final[str] = UNKNOWN

    # Mapping for integer status codes (Domain Enum -> Color)
    _CODE_MAP: Final[Dict[int, str]] = {
        RUNNING_CODE: RUNNING,
        SHUTDOWN_CODE: SHUTDOWN,
        STOPPED_CODE: STOPPED,
        MAINTENANCE_CODE: MAINTENANCE,
        ALARM_CODE: ALARM,
        UNKNOWN_CODE: UNKNOWN,
    }

    # Mapping for integer status codes (Domain Enum -> Name)
    _NAME_MAP: Final[Dict[int, str]] = {
        RUNNING_CODE: "Running",
        SHUTDOWN_CODE: "Shutdown",
        STOPPED_CODE: "Stopped",
        MAINTENANCE_CODE: "Maintenance",
        ALARM_CODE: "Alarm",
        UNKNOWN_CODE: "Unknown",
    }

    @classmethod
    def get_color(cls, status_code: int) -> str:
        """
        Returns the hex color string for a given integer status code.
        Defaults to OFFLINE color if code is unknown.
        """
        return cls._CODE_MAP.get(int(status_code), cls.OFFLINE)

    @classmethod
    def get_name(cls, status_code: int) -> str:
        """
        Returns the display name for a given integer status code.
        Defaults to 'Unknown' if code is missing.
        """
        return cls._NAME_MAP.get(int(status_code), "Unknown")
