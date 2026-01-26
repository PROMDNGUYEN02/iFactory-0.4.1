"""
Application Constants - Single source of truth for immutable values.

This module contains all application-wide constants including:
- Device status codes and colors.
- Time intervals and caching settings.
- Application and UI limits.
- UI default values and dimensions.

All values are immutable and type-safe.
"""

from __future__ import annotations
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from functools import lru_cache
from typing import Final, Union

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:

    class StrEnum(str, Enum):
        """
        String enum backport for Python < 3.11.

        Inherits from both str and Enum, making members usable as strings.
        """

        def __new__(cls, value: str) -> "StrEnum":
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        def __str__(self) -> str:
            return self.value

        def __repr__(self) -> str:
            return f"{self.__class__.__name__}.{self.name}"

        @staticmethod
        def _generate_next_value_(
            name: str, start: int, count: int, last_values: list
        ) -> str:
            return name.lower()


__all__ = [
    "DeviceStatus",
    "StatusDisplay",
    "ThemeMode",
    "StatusColors",
    "UIConstants",
    "TimeConstants",
    "Limits",
    "UIDefaults",
    "get_status_color",
]
logger = logging.getLogger(__name__)


class DeviceStatus(IntEnum):
    """
    Device operational status codes (0-5).

    Values 0-5 map to specific operational states.
    Use `from_value()` for safe parsing from external data.

    Attributes:
        UNKNOWN: Status cannot be determined (0).
        RUNNING: Device is operational (1).
        SHUTDOWN: Device is powered off (2).
        STOP: Device is stopped/idle (3).
        MAINTENANCE: Device under maintenance (4).
        ALARM: Device has active alarm (5).
    """

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOP = 3
    MAINTENANCE = 4
    ALARM = 5

    @classmethod
    def from_value(cls, value: Union[int, str, None]) -> "DeviceStatus":
        """
        Parse status from int, string, or None.

        Args:
            value: Status code (int), string (e.g., "running"), or None.

        Returns:
            Corresponding DeviceStatus enum member (defaults to UNKNOWN).
        """
        if value is None:
            return cls.UNKNOWN
        try:
            int_val = int(value)
            return cls(int_val)
        except (ValueError, TypeError):
            logger.debug(f"Invalid status value received: {value}")
            return cls.UNKNOWN

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        return self.name

    @property
    def color_code(self) -> str:
        """Hex color code for default (light) theme."""
        return _STATUS_COLOR_MAP.get(self, StatusColors.UNKNOWN)


class StatusDisplay(StrEnum):
    """Display names for device statuses."""

    UNKNOWN = "UNKNOWN"
    RUNNING = "RUNNING"
    SHUTDOWN = "SHUTDOWN"
    STOP = "STOP"
    MAINTENANCE = "MAINTENANCE"
    ALARM = "ALARM"


class ThemeMode(StrEnum):
    """
    Application theme modes.

    Attributes:
        LIGHT: Light color scheme.
        DARK: Dark color scheme.
        SYSTEM: Follow system preference.
    """

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"

    @classmethod
    def from_string(cls, value: str) -> "ThemeMode":
        """
        Parse theme from string with fallback.

        Args:
            value: Theme name string.

        Returns:
            ThemeMode (defaults to LIGHT).
        """
        try:
            return cls(value.lower().strip())
        except ValueError:
            logger.debug(f"Unknown theme value: {value}")
            return cls.LIGHT


class StatusColors:
    """
    Immutable color mappings for device statuses.

    Provides static hex codes for different operational states.
    For theme-aware colors, use `get_status_color()` utility.

    Attributes:
        RUNNING: Success/Active color.
        STOP: Warning/Stopped color.
        ALARM: Error/Critical color.
        ...
    """

    __slots__ = ()
    RUNNING: Final[str] = "#4CAF50"
    SHUTDOWN: Final[str] = "#BDBDBD"
    STOP: Final[str] = "#F44336"
    MAINTENANCE: Final[str] = "#03A9F4"
    ALARM: Final[str] = "#FFEB3B"
    UNKNOWN: Final[str] = "#9E9E9E"
    SUCCESS: Final[str] = "#4CAF50"
    WARNING: Final[str] = "#FF9800"
    ERROR: Final[str] = "#F44336"
    INFO: Final[str] = "#2196F3"


class UIConstants:
    """
    Aggregation of UI-related constants.

    Combines dimensions, sizes, and colors used by presentation layer.
    """

    __slots__ = ()
    MENU_EXPANDED_WIDTH: Final[int] = 250
    MENU_COLLAPSED_WIDTH: Final[int] = 60
    RIGHT_PANEL_WIDTH_EXPANDED: Final[int] = 350
    RIGHT_PANEL_MIN: Final[int] = 150
    RIGHT_PANEL_MAX: Final[int] = 1200
    RIGHT_HOVER_ZONE_WIDTH: Final[int] = 200
    ICON_SIZE: Final[int] = 24
    ICON_SIZE_SMALL: Final[int] = 16
    ICON_SIZE_LARGE: Final[int] = 32
    DEFAULT_FONT_SIZE: Final[int] = 12
    MENU_ITEM_HEIGHT: Final[int] = 40
    ANIMATION_DURATION: Final[int] = 300


class TimeConstants:
    """
    Time-related constants for polling, caching, and animations.

    All intervals are in milliseconds unless specified.
    """

    __slots__ = ()
    CACHE_TTL_MS: Final[int] = 30000
    DEBOUNCE_MS: Final[int] = 150
    TOOLTIP_DELAY_MS: Final[int] = 500
    DB_POOL_TIMEOUT: Final[int] = 30
    DB_POOL_RECYCLE: Final[int] = 1800
    HTTP_TIMEOUT: Final[int] = 30
    WEBSOCKET_PING: Final[int] = 30


class Limits:
    """
    Application resource limits to ensure stability.

    These values prevent resource exhaustion and ensure
    predictable performance.
    """

    __slots__ = ()
    MAX_DEVICES: Final[int] = 1000
    MAX_HISTORY_ROWS: Final[int] = 10000
    MAX_CACHE_SIZE: Final[int] = 500
    CHUNK_SIZE: Final[int] = 1000
    MAX_CONCURRENT: Final[int] = 10
    MAX_VISIBLE_DEVICES: Final[int] = 100
    MAX_LOG_LINES: Final[int] = 1000
    POLL_INTERVAL_MS: Final[int] = 5000
    POLL_FAST_MS: Final[int] = 3000
    POLL_SLOW_MS: Final[int] = 10000


class UIDefaults:
    """
    Default values for UI components.

    These can be overridden by user settings or themes.
    """

    __slots__ = ()
    ANIMATION_DURATION: Final[int] = 300
    ICON_SIZE: Final[int] = 24
    ICON_SIZE_SMALL: Final[int] = 16
    ICON_SIZE_LARGE: Final[int] = 32


_STATUS_COLOR_MAP: Final[dict[DeviceStatus, str]] = {
    DeviceStatus.RUNNING: StatusColors.RUNNING,
    DeviceStatus.SHUTDOWN: StatusColors.SHUTDOWN,
    DeviceStatus.STOP: StatusColors.STOP,
    DeviceStatus.MAINTENANCE: StatusColors.MAINTENANCE,
    DeviceStatus.ALARM: StatusColors.ALARM,
    DeviceStatus.UNKNOWN: StatusColors.UNKNOWN,
}
_THEME_LIGHT_MAP: Final[dict[str, str]] = {
    "RUNNING": StatusColors.RUNNING,
    "SHUTDOWN": StatusColors.SHUTDOWN,
    "STOP": StatusColors.STOP,
    "MAINTENANCE": StatusColors.MAINTENANCE,
    "ALARM": StatusColors.ALARM,
    "UNKNOWN": StatusColors.UNKNOWN,
}
_THEME_DARK_MAP: Final[dict[str, str]] = {
    "RUNNING": "#66BB6A",
    "SHUTDOWN": "#757575",
    "STOP": "#EF5350",
    "MAINTENANCE": "#29B6F6",
    "ALARM": "#FFF176",
    "UNKNOWN": "#616161",
}


@lru_cache(maxsize=64)
def get_status_color(
    status: Union[int, str, DeviceStatus], theme: str = "light"
) -> str:
    """
    Get hex color for a device status based on theme.

    Args:
        status: Status enum, code, or string name.
        theme: UI theme ("light" or "dark").

    Returns:
        Hex color string (e.g., "#4CAF50").

    Note:
        This utility provides a centralized way to get colors.
        For production, prefer using Domain Entity's `current_status.color(theme)`.
    """
    if isinstance(status, DeviceStatus):
        status_enum = status
    elif isinstance(status, int):
        status_enum = DeviceStatus.from_value(status)
    elif isinstance(status, str):
        try:
            status_enum = DeviceStatus[status.upper()]
        except KeyError:
            status_enum = DeviceStatus.UNKNOWN
    else:
        status_enum = DeviceStatus.UNKNOWN
    status_name = status_enum.name
    if theme == "dark":
        return _THEME_DARK_MAP.get(status_name, StatusColors.UNKNOWN)
    return _THEME_LIGHT_MAP.get(status_name, StatusColors.UNKNOWN)
