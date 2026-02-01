# File: presentation/constants/status.py
from enum import IntEnum
from typing import Dict, Final


class StatusCode(IntEnum):
    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5


class Status:
    """
    Status configuration - SYNCHRONIZED with Gantt widget colors.
    """

    # Modern color palette matching Gantt widget
    COLORS: Final[Dict[int, str]] = {
        StatusCode.UNKNOWN: "#64748B",  # Slate gray
        StatusCode.RUNNING: "#10B981",  # Emerald green
        StatusCode.SHUTDOWN: "#3B82F6",  # Blue
        StatusCode.STOPPED: "#F59E0B",  # Amber/Orange
        StatusCode.MAINTENANCE: "#8B5CF6",  # Violet
        StatusCode.ALARM: "#EF4444",  # Red
    }

    NAMES: Final[Dict[int, str]] = {
        StatusCode.UNKNOWN: "Unknown",
        StatusCode.RUNNING: "Running",
        StatusCode.SHUTDOWN: "Shutdown",
        StatusCode.STOPPED: "Stopped",
        StatusCode.MAINTENANCE: "Maintenance",
        StatusCode.ALARM: "Alarm",
    }

    EMOJIS: Final[Dict[int, str]] = {
        StatusCode.UNKNOWN: "❓",
        StatusCode.RUNNING: "🟢",
        StatusCode.SHUTDOWN: "🔵",
        StatusCode.STOPPED: "🟡",
        StatusCode.MAINTENANCE: "🟣",
        StatusCode.ALARM: "🔴",
    }

    @classmethod
    def get_color(cls, code: int) -> str:
        return cls.COLORS.get(code, cls.COLORS[StatusCode.UNKNOWN])

    @classmethod
    def get_name(cls, code: int) -> str:
        return cls.NAMES.get(code, cls.NAMES[StatusCode.UNKNOWN])

    @classmethod
    def get_emoji(cls, code: int) -> str:
        return cls.EMOJIS.get(code, cls.EMOJIS[StatusCode.UNKNOWN])


APP_ICON_PATH = ":/icon/icon.ico"


__all__ = ["StatusCode", "Status", "APP_ICON_PATH"]
