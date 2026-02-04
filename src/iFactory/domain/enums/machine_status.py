# src/iFactory/domain/enums/machine_status.py
"""
Machine Status Enumeration.
"""

from __future__ import annotations

from enum import IntEnum, unique
from typing import ClassVar, FrozenSet, Mapping, Optional


@unique
class MachineStatus(IntEnum):
    """Canonical core states of a manufacturing device."""

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5

    _DOWNTIME_STATUSES: ClassVar[FrozenSet[MachineStatus]]
    _ATTENTION_REQUIRED: ClassVar[FrozenSet[MachineStatus]]
    _INACTIVE_STATUSES: ClassVar[FrozenSet[MachineStatus]]
    _IDLE_STATUSES: ClassVar[FrozenSet[MachineStatus]]
    _PRODUCTION_CAPABLE: ClassVar[FrozenSet[MachineStatus]]
    _DISPLAY_NAMES: ClassVar[Mapping[int, str]]
    _DISPLAY_COLORS: ClassVar[Mapping[int, str]]
    _CODE_MAPPING: ClassVar[Mapping[str, MachineStatus]]

    @property
    def implies_downtime(self) -> bool:
        return self in self._DOWNTIME_STATUSES

    @property
    def requires_attention(self) -> bool:
        return self in self._ATTENTION_REQUIRED

    @property
    def is_running(self) -> bool:
        return self == MachineStatus.RUNNING

    @property
    def is_active(self) -> bool:
        return self not in self._INACTIVE_STATUSES

    @property
    def is_idle(self) -> bool:
        return self in self._IDLE_STATUSES

    @property
    def can_produce(self) -> bool:
        return self in self._PRODUCTION_CAPABLE

    @property
    def is_error(self) -> bool:
        return self == MachineStatus.ALARM

    @property
    def display_name(self) -> str:
        return self._DISPLAY_NAMES.get(self.value, self.name.title())

    @property
    def color_key(self) -> str:
        return self._DISPLAY_COLORS.get(self.value, "unknown")

    @classmethod
    def from_value(cls, value: Optional[int | str]) -> MachineStatus:
        """Create from integer or string value."""
        if value is None:
            return cls.UNKNOWN
        try:
            if isinstance(value, str):
                value = int(value)
            return cls(value)
        except (ValueError, TypeError):
            return cls.UNKNOWN

    @classmethod
    def from_code(cls, code: Optional[str]) -> MachineStatus:
        """Create from external system code."""
        if code is None:
            return cls.UNKNOWN

        code_upper = str(code).strip().upper()

        # Check direct mapping
        if code_upper in cls._CODE_MAPPING:
            return cls._CODE_MAPPING[code_upper]

        # Try as integer
        try:
            return cls(int(code))
        except (ValueError, TypeError):
            pass

        # Try as enum name
        try:
            return cls[code_upper]
        except KeyError:
            pass

        return cls.UNKNOWN

    @classmethod
    def from_name(cls, name: Optional[str]) -> MachineStatus:
        """Create from status name."""
        if name is None:
            return cls.UNKNOWN
        try:
            return cls[name.strip().upper()]
        except KeyError:
            return cls.UNKNOWN

    @classmethod
    def all_statuses(cls) -> list[MachineStatus]:
        return list(cls)

    @classmethod
    def downtime_statuses(cls) -> FrozenSet[MachineStatus]:
        return cls._DOWNTIME_STATUSES

    def __str__(self) -> str:
        return self.display_name

    def __repr__(self) -> str:
        return f"MachineStatus.{self.name}"


# Initialize class constants
MachineStatus._DOWNTIME_STATUSES = frozenset(
    {
        MachineStatus.SHUTDOWN,
        MachineStatus.STOPPED,
        MachineStatus.MAINTENANCE,
        MachineStatus.ALARM,
    }
)

MachineStatus._ATTENTION_REQUIRED = frozenset(
    {
        MachineStatus.ALARM,
        MachineStatus.STOPPED,
    }
)

MachineStatus._INACTIVE_STATUSES = frozenset(
    {
        MachineStatus.SHUTDOWN,
        MachineStatus.UNKNOWN,
    }
)

MachineStatus._IDLE_STATUSES = frozenset(
    {
        MachineStatus.STOPPED,
        MachineStatus.UNKNOWN,
    }
)

MachineStatus._PRODUCTION_CAPABLE = frozenset(
    {
        MachineStatus.RUNNING,
        MachineStatus.STOPPED,
    }
)

MachineStatus._DISPLAY_NAMES = {
    0: "Unknown",
    1: "Running",
    2: "Shutdown",
    3: "Stopped",
    4: "Maintenance",
    5: "Alarm",
}

MachineStatus._DISPLAY_COLORS = {
    0: "unknown",
    1: "running",
    2: "shutdown",
    3: "stopped",
    4: "maintenance",
    5: "alarm",
}

MachineStatus._CODE_MAPPING = {
    "0": MachineStatus.UNKNOWN,
    "1": MachineStatus.RUNNING,
    "2": MachineStatus.SHUTDOWN,
    "3": MachineStatus.STOPPED,
    "4": MachineStatus.MAINTENANCE,
    "5": MachineStatus.ALARM,
    "UNK": MachineStatus.UNKNOWN,
    "RUN": MachineStatus.RUNNING,
    "SHT": MachineStatus.SHUTDOWN,
    "STP": MachineStatus.STOPPED,
    "MNT": MachineStatus.MAINTENANCE,
    "ALM": MachineStatus.ALARM,
    "UNKNOWN": MachineStatus.UNKNOWN,
    "RUNNING": MachineStatus.RUNNING,
    "SHUTDOWN": MachineStatus.SHUTDOWN,
    "STOPPED": MachineStatus.STOPPED,
    "MAINTENANCE": MachineStatus.MAINTENANCE,
    "ALARM": MachineStatus.ALARM,
}

__all__ = ["MachineStatus"]
