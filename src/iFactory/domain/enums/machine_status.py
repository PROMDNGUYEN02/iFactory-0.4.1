# src/iFactory/domain/enums/machine_status.py
"""
Machine Status Enumeration.

Defines all possible states a manufacturing device can be in.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, Optional, Set


class MachineStatus(IntEnum):
    """
    Enumeration of possible machine statuses.

    Status values are integers for efficient storage and comparison.

    Categories:
    - Active: RUNNING (producing)
    - Inactive but available: STOPPED
    - Unavailable: SHUTDOWN, MAINTENANCE, ALARM
    - Unknown: Initial state or communication lost
    """

    UNKNOWN = 0
    RUNNING = 1
    STOPPED = 2
    SHUTDOWN = 3
    MAINTENANCE = 4
    ALARM = 5

    # ========================================================================
    # Classification Properties
    # ========================================================================

    @property
    def is_active(self) -> bool:
        """True if device is in an active state (running or stopped)."""
        return self in (MachineStatus.RUNNING, MachineStatus.STOPPED)

    @property
    def is_running(self) -> bool:
        """True if device is actively producing."""
        return self == MachineStatus.RUNNING

    @property
    def is_available(self) -> bool:
        """True if device could potentially run."""
        return self in (MachineStatus.RUNNING, MachineStatus.STOPPED)

    @property
    def implies_downtime(self) -> bool:
        """True if this status represents downtime."""
        return self in (
            MachineStatus.STOPPED,
            MachineStatus.SHUTDOWN,
            MachineStatus.MAINTENANCE,
            MachineStatus.ALARM,
        )

    @property
    def requires_attention(self) -> bool:
        """True if this status requires operator attention."""
        return self in (
            MachineStatus.ALARM,
            MachineStatus.MAINTENANCE,
            MachineStatus.UNKNOWN,
        )

    @property
    def is_critical(self) -> bool:
        """True if this is a critical state."""
        return self == MachineStatus.ALARM

    @property
    def is_planned_downtime(self) -> bool:
        """True if this is planned downtime."""
        return self in (MachineStatus.SHUTDOWN, MachineStatus.MAINTENANCE)

    # ========================================================================
    # Display Properties
    # ========================================================================

    @property
    def display_name(self) -> str:
        """Human-readable name for UI display."""
        return _STATUS_DISPLAY_NAMES.get(self, self.name)

    @property
    def color_code(self) -> str:
        """Color code for visualization."""
        return _STATUS_COLORS.get(self, "#808080")

    @property
    def icon_name(self) -> str:
        """Icon identifier for UI."""
        return _STATUS_ICONS.get(self, "question")

    @property
    def priority(self) -> int:
        """
        Priority for sorting (lower = more important).

        Useful for showing critical statuses first.
        """
        return _STATUS_PRIORITY.get(self, 99)

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def from_code(cls, code: str) -> "MachineStatus":
        """
        Convert status code string to MachineStatus.

        Args:
            code: Status code (e.g., "RUN", "STP", "1", etc.)

        Returns:
            Corresponding MachineStatus

        Note:
            Returns UNKNOWN for unrecognized codes.
        """
        if not code:
            return cls.UNKNOWN

        normalized = str(code).strip().upper()

        # Try direct enum name match
        try:
            return cls[normalized]
        except KeyError:
            pass

        # Try integer value
        try:
            return cls(int(normalized))
        except (ValueError, KeyError):
            pass

        # Try code mapping
        status = _CODE_MAPPING.get(normalized)
        if status is not None:
            return status

        return cls.UNKNOWN

    @classmethod
    def from_value(cls, value: int) -> "MachineStatus":
        """
        Convert integer value to MachineStatus.

        Args:
            value: Status integer value

        Returns:
            Corresponding MachineStatus or UNKNOWN
        """
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN

    # ========================================================================
    # Utility Methods
    # ========================================================================

    @classmethod
    def all_active(cls) -> Set["MachineStatus"]:
        """Return all active statuses."""
        return {s for s in cls if s.is_active}

    @classmethod
    def all_downtime(cls) -> Set["MachineStatus"]:
        """Return all downtime statuses."""
        return {s for s in cls if s.implies_downtime}

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"MachineStatus.{self.name}"


# ============================================================================
# Status Metadata Mappings
# ============================================================================

_STATUS_DISPLAY_NAMES: Dict[MachineStatus, str] = {
    MachineStatus.UNKNOWN: "Unknown",
    MachineStatus.RUNNING: "Running",
    MachineStatus.STOPPED: "Stopped",
    MachineStatus.SHUTDOWN: "Shutdown",
    MachineStatus.MAINTENANCE: "Maintenance",
    MachineStatus.ALARM: "Alarm",
}

_STATUS_COLORS: Dict[MachineStatus, str] = {
    MachineStatus.UNKNOWN: "#808080",  # Gray
    MachineStatus.RUNNING: "#22C55E",  # Green
    MachineStatus.STOPPED: "#F59E0B",  # Yellow/Amber
    MachineStatus.SHUTDOWN: "#6B7280",  # Dark Gray
    MachineStatus.MAINTENANCE: "#3B82F6",  # Blue
    MachineStatus.ALARM: "#EF4444",  # Red
}

_STATUS_ICONS: Dict[MachineStatus, str] = {
    MachineStatus.UNKNOWN: "question",
    MachineStatus.RUNNING: "play",
    MachineStatus.STOPPED: "pause",
    MachineStatus.SHUTDOWN: "power-off",
    MachineStatus.MAINTENANCE: "wrench",
    MachineStatus.ALARM: "exclamation-triangle",
}

_STATUS_PRIORITY: Dict[MachineStatus, int] = {
    MachineStatus.ALARM: 1,
    MachineStatus.UNKNOWN: 2,
    MachineStatus.MAINTENANCE: 3,
    MachineStatus.STOPPED: 4,
    MachineStatus.RUNNING: 5,
    MachineStatus.SHUTDOWN: 6,
}

# Code to status mapping (add your specific codes here)
_CODE_MAPPING: Dict[str, MachineStatus] = {
    # Common abbreviations
    "RUN": MachineStatus.RUNNING,
    "STP": MachineStatus.STOPPED,
    "STOP": MachineStatus.STOPPED,
    "SHT": MachineStatus.SHUTDOWN,
    "SHUT": MachineStatus.SHUTDOWN,
    "MNT": MachineStatus.MAINTENANCE,
    "MAINT": MachineStatus.MAINTENANCE,
    "ALM": MachineStatus.ALARM,
    "ERR": MachineStatus.ALARM,
    "ERROR": MachineStatus.ALARM,
    "UNK": MachineStatus.UNKNOWN,
    # Boolean-like
    "ON": MachineStatus.RUNNING,
    "OFF": MachineStatus.SHUTDOWN,
    "TRUE": MachineStatus.RUNNING,
    "FALSE": MachineStatus.STOPPED,
}


__all__ = ["MachineStatus"]
