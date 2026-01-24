"""
Device History Entity - Represents a time period with a specific status.

This entity is immutable (frozen) and captures a snapshot of a device's
state over a continuous time range. It is the primary building block for
Gantt charts and historical performance analysis.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar
import warnings

from ..enums.device_status import DeviceStatus
from ..exceptions import HistoryMergeError
from .equipment_code import EquipmentCode
from ..value_objects.status import Status
from ..value_objects.time_range import TimeRange

__all__ = ["DeviceHistory"]


@dataclass(frozen=True, slots=True)
class DeviceHistory:
    """
    Immutable entity representing a discrete status period.

    This entity captures a period during which a device maintained
    a specific operational status. It is used for:
    - Generating Gantt chart visualizations
    - Calculating uptime/downtime metrics
    - Analyzing equipment performance

    Invariants:
    - equipment_code is always valid
    - status is always valid
    - time_range.start <= time_range.end

    Attributes:
        equipment_code: The unique identifier for the equipment.
        status: The operational status during this period.
        time_range: The time boundaries of the period.
    """

    equipment_code: EquipmentCode
    status: Status
    time_range: TimeRange

    @classmethod
    def create(cls, code: str, status: str | DeviceStatus, start: datetime, end: datetime) -> "DeviceHistory":
        """
        Create a DeviceHistory from primitive values.

        This is the preferred factory method for creating instances from
        raw data, as it encapsulates Value Object construction.

        Args:
            code: Equipment identifier string.
            status: Status code, name, or DeviceStatus enum.
            start: Period start timestamp.
            end: Period end timestamp.

        Returns:
            A populated DeviceHistory entity.

        Raises:
            InvalidEquipmentCodeError: If code is invalid.
            InvalidTimeRangeError: If time range is invalid.
        """
        if isinstance(status, DeviceStatus):
            status_vo = Status(status)
        else:
            status_vo = Status(DeviceStatus.normalize(status))

        return cls(
            equipment_code=EquipmentCode(code),
            status=status_vo,
            time_range=TimeRange(start, end),
        )

    # === Property Accessors ===

    @property
    def code(self) -> str:
        """Get the string value of the equipment code."""
        return self.equipment_code.value

    @property
    def device_type(self) -> str:
        """Get the device type (prefix of equipment code)."""
        return self.equipment_code.prefix

    @property
    def start_time(self) -> datetime:
        """Get the start time of the period."""
        return self.time_range.start

    @property
    def end_time(self) -> datetime:
        """Get the end time of the period."""
        return self.time_range.end

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return self.time_range.duration_seconds

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.time_range.duration_minutes

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.time_range.duration_hours

    @property
    def status_code(self) -> str:
        """Get the status code string."""
        return self.status.code

    @property
    def status_name(self) -> str:
        """Get the human-readable status name."""
        return self.status.name

    @property
    def display_name(self) -> str:
        """Get display name combining code and status."""
        return f"{self.code}: {self.status_name}"

    @property
    def is_running(self) -> bool:
        """Check if this period represents running status."""
        return self.status.is_running

    @property
    def is_downtime(self) -> bool:
        """Check if this period represents downtime (stopped or alarm)."""
        return self.status.is_stopped or self.status.is_alarm

    # === Domain Behavior ===

    def overlaps(self, other: "DeviceHistory") -> bool:
        """
        Check if this period overlaps with another.

        Args:
            other: Another DeviceHistory instance.

        Returns:
            True if time ranges overlap.
        """
        return self.time_range.overlaps(other.time_range)

    def contains_time(self, dt: datetime) -> bool:
        """
        Check if a datetime falls within this period.

        Args:
            dt: The datetime to check.

        Returns:
            True if dt is within [start, end].
        """
        return self.time_range.contains(dt)

    def is_adjacent_to(self, other: "DeviceHistory") -> bool:
        """
        Check if this period is immediately adjacent to another.

        Args:
            other: Another DeviceHistory instance.

        Returns:
            True if periods are adjacent with no gap.
        """
        return self.time_range.is_adjacent_to(other.time_range)

    def can_merge_with(self, other: "DeviceHistory") -> bool:
        """
        Check if this period can be merged with another.

        Business Rule:
        Periods can be merged if they:
        1. Belong to the same device (same equipment_code)
        2. Have the same status
        3. Are overlapping OR adjacent

        Args:
            other: Another DeviceHistory instance.

        Returns:
            True if periods can be merged.
        """
        if self.equipment_code != other.equipment_code:
            return False
        if self.status != other.status:
            return False
        return self.overlaps(other) or self.is_adjacent_to(other)

    def merge_with(self, other: "DeviceHistory") -> "DeviceHistory":
        """
        Merge this period with another, creating a combined period.

        Business Rule:
        Creates a new period spanning the union of both time ranges.

        Args:
            other: Another DeviceHistory instance.

        Returns:
            A new DeviceHistory covering both periods.

        Raises:
            HistoryMergeError: If periods cannot be merged.
        """
        if self.equipment_code != other.equipment_code:
            raise HistoryMergeError.different_devices(self.code, other.code)

        if self.status != other.status:
            raise HistoryMergeError.different_statuses(self.status_name, other.status_name)

        if not self.overlaps(other) and not self.is_adjacent_to(other):
            gap = self.time_range.gap_to(other.time_range)
            gap_seconds = gap.total_seconds() if gap else 0
            raise HistoryMergeError.non_adjacent(gap_seconds)

        return DeviceHistory(
            equipment_code=self.equipment_code,
            status=self.status,
            time_range=self.time_range.union(other.time_range),
        )

    def split_at(self, dt: datetime) -> tuple["DeviceHistory", "DeviceHistory"] | None:
        """
        Split this period at a specific datetime.

        Args:
            dt: The datetime at which to split.

        Returns:
            Tuple of two DeviceHistory periods, or None if dt is outside range.
        """
        split_ranges = self.time_range.split_at(dt)
        if split_ranges is None:
            return None

        return (
            DeviceHistory(
                equipment_code=self.equipment_code,
                status=self.status,
                time_range=split_ranges[0],
            ),
            DeviceHistory(
                equipment_code=self.equipment_code,
                status=self.status,
                time_range=split_ranges[1],
            ),
        )

    def truncate_to(self, time_range: TimeRange) -> "DeviceHistory | None":
        """
        Truncate this period to fit within a given time range.

        Useful for displaying periods within a specific window.

        Args:
            time_range: The boundary to truncate to.

        Returns:
            A new DeviceHistory truncated to the intersection,
            or None if there is no overlap.
        """
        intersection = self.time_range.intersection(time_range)
        if intersection is None:
            return None

        return DeviceHistory(
            equipment_code=self.equipment_code,
            status=self.status,
            time_range=intersection,
        )

    # === Serialization (for logging/debugging, not for presentation) ===

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to a dictionary representation.

        Note: This method is primarily for debugging and logging.
        For presentation layer data transfer, use dedicated DTOs.

        Returns:
            Dictionary representation containing both light and dark colors.
        """
        return {
            "equip_code": self.code,
            "device_type": self.device_type,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "status_color_light": self.status.color_light.hex_code,
            "status_color_dark": self.status.color_dark.hex_code,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "duration_minutes": self.duration_minutes,
            "is_running": self.is_running,
            "is_downtime": self.is_downtime,
        }

    # === String Representations ===

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"{self.code} [{self.status_name}] " f"{self.time_range.format('%H:%M')} " f"({self.duration_minutes:.1f}m)"

    def __repr__(self) -> str:
        """Debug representation."""
        return f"DeviceHistory(code={self.code!r}, " f"status={self.status_name!r}, " f"start={self.start_time!r}, " f"end={self.end_time!r})"

    # === Comparison ===

    def __lt__(self, other: "DeviceHistory") -> bool:
        """Enable sorting by equipment code, then by start time."""
        if not isinstance(other, DeviceHistory):
            return NotImplemented
        if self.equipment_code != other.equipment_code:
            return self.equipment_code < other.equipment_code
        return self.time_range < other.time_range
