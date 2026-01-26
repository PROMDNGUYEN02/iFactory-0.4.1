from __future__ import annotations
from enum import Enum, unique


@unique
class MachineStatus(Enum):
    """
    Canonical core states of a manufacturing device.
    Strictly business definitions. UI colors and translations are explicitly forbidden here.
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
        return self in (MachineStatus.SHUTDOWN, MachineStatus.MAINTENANCE, MachineStatus.STOPPED, MachineStatus.ALARM)

    @property
    def requires_attention(self) -> bool:
        """Business rule: Determine if operations should be alerted."""
        return self in (MachineStatus.ALARM, MachineStatus.STOPPED)

    @property
    def is_running(self) -> bool:
        return self == MachineStatus.RUNNING

    @classmethod
    def from_business_term(cls, value: str | None) -> MachineStatus:
        """Maps shop-floor vernacular to canonical system states."""
        if not value:
            return cls.UNKNOWN

        clean = str(value).strip().lower()

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
