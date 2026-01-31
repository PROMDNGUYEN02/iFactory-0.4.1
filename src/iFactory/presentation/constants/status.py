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
    COLORS: Final[Dict[int, str]] = {
        StatusCode.UNKNOWN: "#9E9E9E",
        StatusCode.RUNNING: "#2E7D32",
        StatusCode.SHUTDOWN: "#616161",
        StatusCode.STOPPED: "#C62828",
        StatusCode.MAINTENANCE: "#0288D1",
        StatusCode.ALARM: "#F9A825",
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
        StatusCode.SHUTDOWN: "⬛",
        StatusCode.STOPPED: "🟡",
        StatusCode.MAINTENANCE: "🔧",
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
