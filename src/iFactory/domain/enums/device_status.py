"""
Domain: Device Status Enums.
Không chứa mã màu UI (Hex code), chỉ chứa logic nghiệp vụ.
"""

from enum import IntEnum


class DeviceStatus(IntEnum):
    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOP = 3
    MAINTENANCE = 4
    ALARM = 5

    @classmethod
    def from_value(cls, value: int | str | None) -> "DeviceStatus":
        if value is None:
            return cls.UNKNOWN
        try:
            return cls(int(value))
        except (ValueError, TypeError):
            return cls.UNKNOWN
