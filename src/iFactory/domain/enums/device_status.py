from __future__ import annotations
from enum import Enum, unique


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
    def implies_downtime(self) -> bool:
        """Business rule: Determine if status constitutes machine downtime."""
        return self in (DeviceStatus.SHUTDOWN, DeviceStatus.MAINTENANCE, DeviceStatus.STOP, DeviceStatus.ALARM)

    @classmethod
    def from_code(cls, code: str | None) -> DeviceStatus:
        if not code:
            return cls.UNKNOWN
        clean_code = str(code).strip()
        for status in cls:
            if status.code == clean_code:
                return status
        return cls.UNKNOWN

    @classmethod
    def from_string(cls, value: str | None) -> DeviceStatus:
        """
        Domain factory logic to convert business vernacular into canonical states.
        Replaces external 'StatusNormalizationService'.
        """
        if not value:
            return cls.UNKNOWN

        clean = str(value).strip().lower()

        # Direct match
        for status in cls:
            if status.code == clean or status.internal_name == clean:
                return status

        # Business vernacular aliases
        aliases = {
            "run": cls.RUNNING,
            "active": cls.RUNNING,
            "on": cls.RUNNING,
            "off": cls.SHUTDOWN,
            "idle": cls.STOP,
            "stopped": cls.STOP,
            "fault": cls.ALARM,
            "error": cls.ALARM,
            "pm": cls.MAINTENANCE,
        }
        return aliases.get(clean, cls.UNKNOWN)
