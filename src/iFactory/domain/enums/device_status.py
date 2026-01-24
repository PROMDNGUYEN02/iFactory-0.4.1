"""
Device Status Enumeration - Domain-only status values.

This module defines of core DeviceStatus enum with business semantics only.
UI-related concerns (colors, emojis, display text) are handled by Presentation layer.

Business Rules:
    - UNKNOWN: Default state when status cannot be determined
    - RUNNING: Device is actively operating
    - SHUTDOWN: Device is powered off
    - STOP: Device stopped unexpectedly (attention required)
    - MAINTENANCE: Device under planned maintenance
    - ALARM: Device triggered an alarm (critical attention required)
"""

from __future__ import annotations

from enum import Enum, unique

__all__ = ["DeviceStatus", "StatusCode"]


class StatusCode:
    """
    Simple database status codes.

    Represents raw string values stored in database (0-5).
    Separate from DeviceStatus to avoid code duplication.
    """

    UNKNOWN = "0"
    RUNNING = "1"
    SHUTDOWN = "2"
    STOP = "3"
    MAINTENANCE = "4"
    ALARM = "5"


@unique
class DeviceStatus(Enum):
    """
    Device status with business semantics only.

    This enum contains ONLY business-meaningful data:
        - internal_name: Snake_case identifier for business logic
        - code: Database code for persistence

    UI concerns (colors, emojis, display text) are handled by Presentation layer.
    """

    UNKNOWN = ("unknown", "0")
    RUNNING = ("running", "1")
    SHUTDOWN = ("shutdown", "2")
    STOP = ("stop", "3")
    MAINTENANCE = ("maintenance", "4")
    ALARM = ("alarm", "5")

    def __init__(
        self,
        internal_name: str,
        code: str,
    ) -> None:
        """
        Initialize status enum member.

        Args:
            internal_name: Snake_case business identifier
            code: Database code string
        """
        self._internal_name = internal_name
        self._code = code

    @property
    def internal_name(self) -> str:
        """Get snake_case internal identifier (e.g., 'running')."""
        return self._internal_name

    @property
    def code(self) -> str:
        """Get database code string (e.g., '1')."""
        return self._code

    @property
    def severity(self) -> int:
        """
        Get severity level of this status for ordering.

        Business Rule:
            -1 = Unknown (indeterminate state)
             0 = Normal (Running)
             1 = Inactive (Shutdown, Maintenance)
             2 = Warning (Stop)
             3 = Critical (Alarm)

        Returns:
            Integer severity level (-1 to 3).
        """
        severity_map = {
            DeviceStatus.UNKNOWN: -1,
            DeviceStatus.RUNNING: 0,
            DeviceStatus.SHUTDOWN: 1,
            DeviceStatus.MAINTENANCE: 1,
            DeviceStatus.STOP: 2,
            DeviceStatus.ALARM: 3,
        }
        return severity_map.get(self, -1)

    @property
    def category(self) -> str:
        """
        Get status category for grouping.

        Business Rule:
            Groups statuses into high-level operational categories.

        Returns:
            One of: 'running', 'stopped', 'alarm', 'inactive', 'unknown'
        """
        if self == DeviceStatus.RUNNING:
            return "running"
        if self == DeviceStatus.STOP:
            return "stopped"
        if self == DeviceStatus.ALARM:
            return "alarm"
        if self in (DeviceStatus.SHUTDOWN, DeviceStatus.MAINTENANCE):
            return "inactive"
        return "unknown"

    @property
    def is_running(self) -> bool:
        """Check if this status represents active operation."""
        return self == DeviceStatus.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Check if this status represents a stopped state."""
        return self == DeviceStatus.STOP

    @property
    def is_alarm(self) -> bool:
        """Check if this status represents an alarm state."""
        return self == DeviceStatus.ALARM

    @property
    def is_maintenance(self) -> bool:
        """Check if this status represents maintenance."""
        return self == DeviceStatus.MAINTENANCE

    @property
    def is_shutdown(self) -> bool:
        """Check if this status represents shutdown."""
        return self == DeviceStatus.SHUTDOWN

    @property
    def is_unknown(self) -> bool:
        """Check if this status represents unknown."""
        return self == DeviceStatus.UNKNOWN

    @property
    def is_inactive(self) -> bool:
        """Check if this status represents an inactive state (stop, shutdown, unknown)."""
        return self in (
            DeviceStatus.STOP,
            DeviceStatus.SHUTDOWN,
            DeviceStatus.UNKNOWN,
        )

    @property
    def is_active(self) -> bool:
        """Check if this status represents active operation (running or maintenance)."""
        return self in (DeviceStatus.RUNNING, DeviceStatus.MAINTENANCE)

    @property
    def requires_attention(self) -> bool:
        """Check if this status requires operator attention."""
        return self in (DeviceStatus.ALARM, DeviceStatus.STOP)

    @classmethod
    def from_code(cls, code: str | None) -> "DeviceStatus":
        """
        Retrieve status by database code.

        Args:
            code: Database code string (e.g., '1')

        Returns:
            DeviceStatus enum member, or UNKNOWN if not found.
        """
        if code is None:
            return cls.UNKNOWN
        clean_code = str(code).strip()
        for status in cls:
            if status.code == clean_code:
                return status
        return cls.UNKNOWN

    @classmethod
    def from_name(cls, name: str | None) -> "DeviceStatus":
        """
        Retrieve status by internal name.

        Args:
            name: Internal name (e.g., 'running')

        Returns:
            DeviceStatus enum member, or UNKNOWN if not found.
        """
        if name is None:
            return cls.UNKNOWN
        clean_name = name.lower().strip()
        for status in cls:
            if status.internal_name == clean_name:
                return status
        return cls.UNKNOWN

    @classmethod
    def from_code_or_name(cls, value: str | None) -> "DeviceStatus":
        """
        Retrieve status by code or name.

        Args:
            value: Either database code or internal name

        Returns:
            DeviceStatus enum member, or UNKNOWN if not found.
        """
        if value is None:
            return cls.UNKNOWN
        clean = str(value).strip()
        for status in cls:
            if status.code == clean or status.internal_name == clean.lower():
                return status
        return cls.UNKNOWN

    @classmethod
    def all_statuses(cls) -> list["DeviceStatus"]:
        """Get a list of all defined statuses."""
        return list(cls)

    @classmethod
    def all_codes(cls) -> list[str]:
        """Get a list of all valid database codes."""
        return [s.code for s in cls]

    @classmethod
    def running_statuses(cls) -> frozenset["DeviceStatus"]:
        """Get all statuses that represent running/active state."""
        return frozenset({cls.RUNNING})

    @classmethod
    def stopped_statuses(cls) -> frozenset["DeviceStatus"]:
        """Get all statuses that represent stopped state."""
        return frozenset({cls.STOP})

    @classmethod
    def alarm_statuses(cls) -> frozenset["DeviceStatus"]:
        """Get all statuses that represent alarm/error state."""
        return frozenset({cls.ALARM})

    @classmethod
    def inactive_statuses(cls) -> frozenset["DeviceStatus"]:
        """Get all statuses that represent inactive state."""
        return frozenset({cls.SHUTDOWN, cls.MAINTENANCE})

    @classmethod
    def attention_required_statuses(cls) -> frozenset["DeviceStatus"]:
        """Get all statuses that require operator attention."""
        return frozenset({cls.ALARM, cls.STOP})

    def __str__(self) -> str:
        """String representation returns internal name."""
        return self._internal_name

    def __repr__(self) -> str:
        """Debug representation returns Enum member name."""
        return f"DeviceStatus.{self.name}"
