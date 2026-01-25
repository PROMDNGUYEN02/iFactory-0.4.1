from __future__ import annotations
from ..enums.device_status import DeviceStatus


class StatusNormalizationService:
    _MAP = {
        "run": DeviceStatus.RUNNING,
        "active": DeviceStatus.RUNNING,
        "on": DeviceStatus.RUNNING,
        "off": DeviceStatus.SHUTDOWN,
        "idle": DeviceStatus.STOP,
        "stopped": DeviceStatus.STOP,
        "fault": DeviceStatus.ALARM,
        "error": DeviceStatus.ALARM,
        "pm": DeviceStatus.MAINTENANCE,
    }

    @classmethod
    def normalize(cls, raw: str | None) -> DeviceStatus:
        if not raw:
            return DeviceStatus.UNKNOWN
        clean = raw.strip().lower()

        # Check direct mapping
        status = DeviceStatus.from_code_or_name(clean)
        if status != DeviceStatus.UNKNOWN:
            return status

        # Check alias mapping
        return cls._MAP.get(clean, DeviceStatus.UNKNOWN)
