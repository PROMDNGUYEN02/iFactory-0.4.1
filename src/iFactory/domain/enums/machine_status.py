from __future__ import annotations

from enum import IntEnum, unique


@unique
class MachineStatus(IntEnum):
    """
    Canonical core states of a manufacturing device.
    """

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5

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
