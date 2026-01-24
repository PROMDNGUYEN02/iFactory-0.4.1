"""
Status Value Object - Immutable status representation.

This Value Object wraps DeviceStatus enum to provide domain-specific semantics.
Only contains business semantics, NO UI concerns (colors, emojis, display text).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums.device_status import DeviceStatus

__all__ = ["Status"]


@dataclass(frozen=True, slots=True)
class Status:
    """
    Immutable status value object with business semantics.

    This class wraps the DeviceStatus enum to provide a rich
    domain object that can be easily extended or replaced.

    Attributes:
        device_status: The underlying DeviceStatus enum member.

    Invariants:
        - Always contains a valid DeviceStatus enum
        - Immutable (frozen=True)
    """

    device_status: DeviceStatus

    @classmethod
    def from_code(cls, code: str | None) -> "Status":
        """
        Create a Status from a database code.

        Args:
            code: Database code string (e.g., '1')

        Returns:
            Status object with DeviceStatus enum.
        """
        return cls(DeviceStatus.from_code(code))

    @classmethod
    def from_name(cls, name: str | None) -> "Status":
        """
        Create a Status from an internal name.

        Args:
            name: Internal name (e.g., 'running')

        Returns:
            Status object with DeviceStatus enum.
        """
        return cls(DeviceStatus.from_name(name))

    @classmethod
    def normalize(cls, value: str | None) -> "Status":
        """
        Create a Status from any input format.

        Args:
            value: Database code or internal name

        Returns:
            Status object with normalized DeviceStatus enum.
        """
        return cls(DeviceStatus.from_code_or_name(value))

    @classmethod
    def unknown(cls) -> "Status":
        """Create a Status representing 'unknown'."""
        return cls(DeviceStatus.UNKNOWN)

    @classmethod
    def running(cls) -> "Status":
        """Create a Status representing 'running'."""
        return cls(DeviceStatus.RUNNING)

    @classmethod
    def shutdown(cls) -> "Status":
        """Create a Status representing 'shutdown'."""
        return cls(DeviceStatus.SHUTDOWN)

    @classmethod
    def stop(cls) -> "Status":
        """Create a Status representing 'stop'."""
        return cls(DeviceStatus.STOP)

    @classmethod
    def alarm(cls) -> "Status":
        """Create a Status representing 'alarm'."""
        return cls(DeviceStatus.ALARM)

    @classmethod
    def maintenance(cls) -> "Status":
        """Create a Status representing 'maintenance'."""
        return cls(DeviceStatus.MAINTENANCE)

    @property
    def code(self) -> str:
        """Get the database code string (e.g., '1')."""
        return self.device_status.code

    @property
    def name(self) -> str:
        """Get the internal snake_case name (e.g., 'running')."""
        return self.device_status.internal_name

    @property
    def severity(self) -> int:
        """
        Get the severity level for ordering and comparison.

        Returns:
            -1 = Unknown
             0 = Normal (Running)
             1 = Inactive (Shutdown, Maintenance)
             2 = Warning (Stop)
             3 = Critical (Alarm)
        """
        return self.device_status.severity

    @property
    def category(self) -> str:
        """Get the status category (running, stopped, alarm, inactive, unknown)."""
        return self.device_status.category

    @property
    def is_running(self) -> bool:
        """Check if the status is 'running'."""
        return self.device_status == DeviceStatus.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Check if the status is 'stop'."""
        return self.device_status == DeviceStatus.STOP

    @property
    def is_alarm(self) -> bool:
        """Check if the status is 'alarm'."""
        return self.device_status == DeviceStatus.ALARM

    @property
    def is_maintenance(self) -> bool:
        """Check if the status is 'maintenance'."""
        return self.device_status == DeviceStatus.MAINTENANCE

    @property
    def is_shutdown(self) -> bool:
        """Check if the status is 'shutdown'."""
        return self.device_status == DeviceStatus.SHUTDOWN

    @property
    def is_unknown(self) -> bool:
        """Check if the status is 'unknown'."""
        return self.device_status == DeviceStatus.UNKNOWN

    @property
    def is_active(self) -> bool:
        """Check if the device is considered active (running or maintenance)."""
        return self.device_status in (DeviceStatus.RUNNING, DeviceStatus.MAINTENANCE)

    @property
    def is_inactive(self) -> bool:
        """Check if the device is considered inactive (stop, shutdown, unknown)."""
        return self.device_status in (
            DeviceStatus.STOP,
            DeviceStatus.SHUTDOWN,
            DeviceStatus.UNKNOWN,
        )

    @property
    def requires_attention(self) -> bool:
        """Check if the status requires operator attention (alarm or stop)."""
        return self.device_status in (DeviceStatus.ALARM, DeviceStatus.STOP)

    def is_same_category(self, other: "Status") -> bool:
        """
        Check if two statuses are in the same operational category.

        Categories: running, stopped, alarm, inactive, unknown

        Args:
            other: Another Status object

        Returns:
            True if categories match.
        """
        return self.category == other.category

    def is_worse_than(self, other: "Status") -> bool:
        """
        Check if this status is more severe than another.

        Args:
            other: Another Status object

        Returns:
            True if this status has higher severity.
        """
        return self.severity > other.severity

    def is_better_than(self, other: "Status") -> bool:
        """
        Check if this status is less severe than another.

        Args:
            other: Another Status object

        Returns:
            True if this status has lower severity and >= 0.
        """
        return self.severity < other.severity and self.severity >= 0

    def __eq__(self, other: object) -> bool:
        """Check equality with Status, DeviceStatus, or string."""
        if isinstance(other, Status):
            return self.device_status == other.device_status
        if isinstance(other, DeviceStatus):
            return self.device_status == other
        if isinstance(other, str):
            return self.name == other or self.code == other
        return False

    def __hash__(self) -> int:
        """Hash based on the underlying enum."""
        return hash(self.device_status)

    def __lt__(self, other: "Status") -> bool:
        """Enable sorting by severity."""
        if isinstance(other, Status):
            return self.severity < other.severity
        return NotImplemented

    def __le__(self, other: "Status") -> bool:
        """Enable sorting by severity."""
        if isinstance(other, Status):
            return self.severity <= other.severity
        return NotImplemented

    def __str__(self) -> str:
        """String representation returns the internal name."""
        return self.name

    def __repr__(self) -> str:
        """Debug representation."""
        return f"Status({self.device_status.name})"
