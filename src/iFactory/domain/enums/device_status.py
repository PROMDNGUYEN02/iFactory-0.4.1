from __future__ import annotations
from enum import Enum, unique


class StatusCode:
    UNKNOWN = "0"
    RUNNING = "1"
    SHUTDOWN = "2"
    STOP = "3"
    MAINTENANCE = "4"
    ALARM = "5"


@unique
class DeviceStatus(Enum):
    UNKNOWN = ("unknown", "0")
    RUNNING = ("running", "1")
    SHUTDOWN = ("shutdown", "2")
    STOP = ("stop", "3")
    MAINTENANCE = ("maintenance", "4")
    ALARM = ("alarm", "5")

    def __init__(self, internal_name: str, code: str) -> None:
        self._internal_name = internal_name
        self._code = code

    @property
    def internal_name(self) -> str:
        return self._internal_name

    @property
    def code(self) -> str:
        return self._code

    @property
    def severity(self) -> int:
        severity_map = {
            DeviceStatus.UNKNOWN: -1,
            DeviceStatus.RUNNING: 0,
            DeviceStatus.SHUTDOWN: 1,
            DeviceStatus.MAINTENANCE: 1,
            DeviceStatus.STOP: 2,
            DeviceStatus.ALARM: 3,
        }
        return severity_map.get(self, -1)

    @property
    def category(self) -> str:
        if self == DeviceStatus.RUNNING:
            return "running"
        if self == DeviceStatus.STOP:
            return "stopped"
        if self == DeviceStatus.ALARM:
            return "alarm"
        if self in (DeviceStatus.SHUTDOWN, DeviceStatus.MAINTENANCE):
            return "inactive"
        return "unknown"

    @classmethod
    def from_code(cls, code: str | None) -> DeviceStatus:
        if code is None:
            return cls.UNKNOWN
        clean_code = str(code).strip()
        for status in cls:
            if status.code == clean_code:
                return status
        return cls.UNKNOWN

    @classmethod
    def from_code_or_name(cls, value: str | None) -> DeviceStatus:
        if value is None:
            return cls.UNKNOWN
        clean = str(value).strip().lower()
        for status in cls:
            if status.code == clean or status.internal_name == clean:
                return status
        return cls.UNKNOWN
