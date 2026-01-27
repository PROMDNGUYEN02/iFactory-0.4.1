from __future__ import annotations

from enum import IntEnum, unique
from typing import Dict


@unique
class MachineStatus(IntEnum):
    """
    Canonical core states of a manufacturing device.

    Uses IntEnum for efficient storage, comparison, and database compatibility.
    All business rules about status semantics are encapsulated here.
    """

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5

    @property
    def display_name(self) -> str:
        return _DISPLAY_NAMES.get(self, self.name.capitalize())

    @property
    def implies_downtime(self) -> bool:
        return self in _DOWNTIME_STATUSES

    @property
    def requires_attention(self) -> bool:
        return self in _ATTENTION_REQUIRED_STATUSES

    @property
    def is_running(self) -> bool:
        return self == MachineStatus.RUNNING

    @property
    def is_active(self) -> bool:
        return self not in _INACTIVE_STATUSES

    @property
    def is_idle(self) -> bool:
        return self in _IDLE_STATUSES

    @property
    def can_produce(self) -> bool:
        return self in _PRODUCTION_CAPABLE_STATUSES

    @classmethod
    def from_raw_value(cls, value: str | int | None) -> MachineStatus:
        if value is None:
            return cls.UNKNOWN

        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                return cls.UNKNOWN

        cleaned = str(value).strip().lower()

        if cleaned.isdigit():
            try:
                return cls(int(cleaned))
            except ValueError:
                return cls.UNKNOWN

        return _ALIASES.get(cleaned, cls.UNKNOWN)

    @classmethod
    def production_statuses(cls) -> tuple[MachineStatus, ...]:
        return (cls.RUNNING,)

    @classmethod
    def non_production_statuses(cls) -> tuple[MachineStatus, ...]:
        return (cls.SHUTDOWN, cls.STOPPED, cls.MAINTENANCE, cls.ALARM, cls.UNKNOWN)


_DISPLAY_NAMES: Dict[MachineStatus, str] = {
    MachineStatus.UNKNOWN: "Unknown",
    MachineStatus.RUNNING: "Running",
    MachineStatus.SHUTDOWN: "Shutdown",
    MachineStatus.STOPPED: "Stopped",
    MachineStatus.MAINTENANCE: "Maintenance",
    MachineStatus.ALARM: "Alarm",
}

_DOWNTIME_STATUSES = frozenset(
    {
        MachineStatus.SHUTDOWN,
        MachineStatus.STOPPED,
        MachineStatus.MAINTENANCE,
        MachineStatus.ALARM,
    }
)

_ATTENTION_REQUIRED_STATUSES = frozenset(
    {
        MachineStatus.ALARM,
        MachineStatus.STOPPED,
    }
)

_INACTIVE_STATUSES = frozenset(
    {
        MachineStatus.SHUTDOWN,
        MachineStatus.UNKNOWN,
    }
)

_IDLE_STATUSES = frozenset(
    {
        MachineStatus.STOPPED,
        MachineStatus.UNKNOWN,
    }
)

_PRODUCTION_CAPABLE_STATUSES = frozenset(
    {
        MachineStatus.RUNNING,
        MachineStatus.STOPPED,
    }
)

_ALIASES: Dict[str, MachineStatus] = {
    "run": MachineStatus.RUNNING,
    "running": MachineStatus.RUNNING,
    "active": MachineStatus.RUNNING,
    "on": MachineStatus.RUNNING,
    "producing": MachineStatus.RUNNING,
    "off": MachineStatus.SHUTDOWN,
    "shutdown": MachineStatus.SHUTDOWN,
    "down": MachineStatus.SHUTDOWN,
    "idle": MachineStatus.STOPPED,
    "stop": MachineStatus.STOPPED,
    "stopped": MachineStatus.STOPPED,
    "pause": MachineStatus.STOPPED,
    "paused": MachineStatus.STOPPED,
    "fault": MachineStatus.ALARM,
    "error": MachineStatus.ALARM,
    "alarm": MachineStatus.ALARM,
    "alert": MachineStatus.ALARM,
    "warning": MachineStatus.ALARM,
    "pm": MachineStatus.MAINTENANCE,
    "maintenance": MachineStatus.MAINTENANCE,
    "maint": MachineStatus.MAINTENANCE,
    "service": MachineStatus.MAINTENANCE,
    "unknown": MachineStatus.UNKNOWN,
    "none": MachineStatus.UNKNOWN,
    "na": MachineStatus.UNKNOWN,
    "n/a": MachineStatus.UNKNOWN,
}
