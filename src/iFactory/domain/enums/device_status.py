from __future__ import annotations
from enum import Enum, unique


@unique
class DeviceStatus(Enum):
    """
    Canonical core states of a manufacturing device.
    Strictly business definitions. No UI colors or strings allowed.
    """

    UNKNOWN = "unknown"
    RUNNING = "running"
    SHUTDOWN = "shutdown"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    ALARM = "alarm"

    @property
    def implies_downtime(self) -> bool:
        """Business rule: Determine if status constitutes machine downtime."""
        return self in (DeviceStatus.SHUTDOWN, DeviceStatus.MAINTENANCE, DeviceStatus.STOPPED, DeviceStatus.ALARM)

    @classmethod
    def from_business_term(cls, value: str | None) -> DeviceStatus:
        """
        Maps shop-floor vernacular to canonical system states.
        This captures the domain language invariant (e.g., 'PM' means Maintenance).
        """
        if not value:
            return cls.UNKNOWN

        clean = str(value).strip().lower()

        # Business vernacular dictionary
        aliases = {
            "run": cls.RUNNING,
            "active": cls.RUNNING,
            "on": cls.RUNNING,
            "off": cls.SHUTDOWN,
            "idle": cls.STOPPED,
            "stop": cls.STOPPED,
            "fault": cls.ALARM,
            "error": cls.ALARM,
            "pm": cls.MAINTENANCE,
        }

        if clean in aliases:
            return aliases[clean]

        try:
            return cls(clean)
        except ValueError:
            return cls.UNKNOWN
