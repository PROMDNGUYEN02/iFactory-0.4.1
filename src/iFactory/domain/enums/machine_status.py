# src/iFactory/domain/enums/machine_status.py
"""
Domain: Machine Status Enumeration.

Canonical core states of a manufacturing device with rich behavior.
"""

from __future__ import annotations

from enum import IntEnum, unique
from functools import cached_property
from typing import ClassVar, FrozenSet, Mapping


@unique
class MachineStatus(IntEnum):
    """
    Canonical core states of a manufacturing device.

    Encapsulates state classifications and business rules.
    Uses IntEnum for database compatibility while providing
    rich domain behavior through properties.

    Status Values:
        UNKNOWN (0): Initial/undefined state
        RUNNING (1): Normal production
        SHUTDOWN (2): Planned shutdown
        STOPPED (3): Temporary stop (can resume)
        MAINTENANCE (4): Under maintenance
        ALARM (5): Error/alarm condition

    Usage:
        status = MachineStatus.RUNNING
        if status.is_active:
            print("Device is active")

        if status.implies_downtime:
            log_downtime(device)
    """

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5

    # ========================================================================
    # Class-level Constants (initialized after class definition)
    # ========================================================================

    _DOWNTIME_STATUSES: ClassVar[FrozenSet["MachineStatus"]]
    _ATTENTION_REQUIRED: ClassVar[FrozenSet["MachineStatus"]]
    _INACTIVE_STATUSES: ClassVar[FrozenSet["MachineStatus"]]
    _IDLE_STATUSES: ClassVar[FrozenSet["MachineStatus"]]
    _PRODUCTION_CAPABLE: ClassVar[FrozenSet["MachineStatus"]]

    # Display configuration
    _DISPLAY_NAMES: ClassVar[Mapping[int, str]]
    _DISPLAY_COLORS: ClassVar[Mapping[int, str]]

    # ========================================================================
    # Business Logic Properties
    # ========================================================================

    @property
    def implies_downtime(self) -> bool:
        """True if this status means the device is not producing."""
        return self in self._DOWNTIME_STATUSES

    @property
    def requires_attention(self) -> bool:
        """True if this status requires operator attention."""
        return self in self._ATTENTION_REQUIRED

    @property
    def is_running(self) -> bool:
        """True if device is actively producing."""
        return self == MachineStatus.RUNNING

    @property
    def is_active(self) -> bool:
        """True if device is not in a shutdown or unknown state."""
        return self not in self._INACTIVE_STATUSES

    @property
    def is_idle(self) -> bool:
        """True if device is idle but available."""
        return self in self._IDLE_STATUSES

    @property
    def can_produce(self) -> bool:
        """True if device is capable of starting production."""
        return self in self._PRODUCTION_CAPABLE

    @property
    def is_error(self) -> bool:
        """True if device is in an error/alarm state."""
        return self == MachineStatus.ALARM

    # ========================================================================
    # Display Properties
    # ========================================================================

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        return self._DISPLAY_NAMES.get(self.value, self.name.title())

    @property
    def color_key(self) -> str:
        """Color key for UI theming (e.g., 'running', 'alarm')."""
        return self._DISPLAY_COLORS.get(self.value, "unknown")

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def from_value(cls, value: int | str | None) -> "MachineStatus":
        """
        Safely create MachineStatus from various input types.

        Args:
            value: Integer, string, or None

        Returns:
            MachineStatus instance (defaults to UNKNOWN if invalid)
        """
        if value is None:
            return cls.UNKNOWN

        try:
            if isinstance(value, str):
                value = int(value)
            return cls(value)
        except (ValueError, TypeError):
            return cls.UNKNOWN

    @classmethod
    def from_name(cls, name: str) -> "MachineStatus":
        """
        Create MachineStatus from status name.

        Args:
            name: Status name (case-insensitive)

        Returns:
            MachineStatus instance (defaults to UNKNOWN if not found)
        """
        try:
            return cls[name.upper()]
        except KeyError:
            return cls.UNKNOWN

    # ========================================================================
    # Utility Methods
    # ========================================================================

    @classmethod
    def all_statuses(cls) -> list["MachineStatus"]:
        """Get all status values."""
        return list(cls)

    @classmethod
    def downtime_statuses(cls) -> FrozenSet["MachineStatus"]:
        """Get all statuses that imply downtime."""
        return cls._DOWNTIME_STATUSES

    @classmethod
    def production_statuses(cls) -> FrozenSet["MachineStatus"]:
        """Get all statuses where production is possible."""
        return cls._PRODUCTION_CAPABLE

    def __str__(self) -> str:
        return self.display_name

    def __repr__(self) -> str:
        return f"MachineStatus.{self.name}"


# ============================================================================
# Initialize Class Constants (after class definition)
# ============================================================================

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


__all__ = ["MachineStatus"]
