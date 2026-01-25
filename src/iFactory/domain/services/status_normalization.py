from __future__ import annotations

from ..enums.device_status import DeviceStatus


class StatusNormalizationService:
    _NORMALIZATION_MAP = {
        "unknown": DeviceStatus.UNKNOWN,
        "running": DeviceStatus.RUNNING,
        "shutdown": DeviceStatus.SHUTDOWN,
        "stop": DeviceStatus.STOP,
        "maintenance": DeviceStatus.MAINTENANCE,
        "alarm": DeviceStatus.ALARM,
        "run": DeviceStatus.RUNNING,
        "active": DeviceStatus.RUNNING,
        "on": DeviceStatus.RUNNING,
        "off": DeviceStatus.SHUTDOWN,
        "stopped": DeviceStatus.STOP,
        "idle": DeviceStatus.STOP,
        "maint": DeviceStatus.MAINTENANCE,
        "pm": DeviceStatus.MAINTENANCE,
        "error": DeviceStatus.ALARM,
        "fault": DeviceStatus.ALARM,
        "warning": DeviceStatus.ALARM,
    }

    @classmethod
    def normalize(cls, value: str | None) -> DeviceStatus:
        if value is None:
            return DeviceStatus.UNKNOWN
        clean = str(value).strip().lower()
        return cls._NORMALIZATION_MAP.get(clean, DeviceStatus.UNKNOWN)

    @classmethod
    def is_valid(cls, value: str | None) -> bool:
        if value is None:
            return False
        return str(value).strip().lower() in cls._NORMALIZATION_MAP
