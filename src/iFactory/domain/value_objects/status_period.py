# src/iFactory/domain/value_objects/status_period.py
"""
Status Period Value Object.

Represents a continuous period during which a device maintained a specific status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..common.value_object import ValueObject
from ..enums.machine_status import MachineStatus
from ..exceptions.domain_exceptions import StatusMergeError
from .equipment_code import EquipmentCode
from .time_range import TimeRange


class StatusPeriod(ValueObject):
    """
    Immutable Value Object representing a continuous period during which
    a device maintained a specific status.

    Used for:
    - History tracking
    - OEE calculations
    - Gantt chart visualization
    - Downtime analysis

    Usage:
        period = StatusPeriod(
            equipment_code=EquipmentCode.create("CNC-001"),
            status=MachineStatus.RUNNING,
            time_range=TimeRange.between(start, end)
        )

        # Get duration
        print(f"Duration: {period.duration_seconds}s")

        # Merge adjacent periods
        if period1.can_merge_with(period2):
            merged = period1.merge_with(period2)
    """

    __slots__ = ("_equipment_code", "_status", "_time_range")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        status: MachineStatus,
        time_range: TimeRange,
    ) -> None:
        """
        Create StatusPeriod.

        Args:
            equipment_code: Device this period belongs to
            status: Status during this period
            time_range: Time range of this period
        """
        self._equipment_code = equipment_code
        self._status = status
        self._time_range = time_range

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def create(
        cls,
        equipment_code: str | EquipmentCode,
        status: MachineStatus | int,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> "StatusPeriod":
        """
        Factory method with flexible input types.

        Args:
            equipment_code: Code as string or EquipmentCode
            status: Status as MachineStatus or integer
            start: Start time
            end: End time (None for ongoing)
        """
        code = equipment_code if isinstance(equipment_code, EquipmentCode) else EquipmentCode.create(equipment_code)
        stat = status if isinstance(status, MachineStatus) else MachineStatus(status)
        time_range = TimeRange(start, end)
        return cls(code, stat, time_range)

    @classmethod
    def ongoing(
        cls,
        equipment_code: EquipmentCode,
        status: MachineStatus,
        start: datetime,
    ) -> "StatusPeriod":
        """Create an ongoing (open-ended) status period."""
        return cls(equipment_code, status, TimeRange.starting_from(start))

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def equipment_code(self) -> EquipmentCode:
        """Device this period belongs to."""
        return self._equipment_code

    @property
    def status(self) -> MachineStatus:
        """Status during this period."""
        return self._status

    @property
    def time_range(self) -> TimeRange:
        """Time range of this period."""
        return self._time_range

    @property
    def start(self) -> datetime:
        """Start time of this period."""
        return self._time_range.start

    @property
    def end(self) -> Optional[datetime]:
        """End time of this period (None if ongoing)."""
        return self._time_range.end

    @property
    def is_ongoing(self) -> bool:
        """True if period has no end."""
        return self._time_range.is_ongoing

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self._time_range.duration_seconds

    @property
    def is_downtime(self) -> bool:
        """True if this is a downtime period."""
        return self._status.implies_downtime

    @property
    def is_productive(self) -> bool:
        """True if this is a productive (running) period."""
        return self._status.is_running

    # ========================================================================
    # Methods
    # ========================================================================

    def with_end_time(self, end: datetime) -> "StatusPeriod":
        """Create new period with specified end time."""
        safe_end = max(end, self._time_range.start)
        return StatusPeriod(
            equipment_code=self._equipment_code,
            status=self._status,
            time_range=TimeRange(self._time_range.start, safe_end),
        )

    def close_at(self, end: datetime) -> "StatusPeriod":
        """Alias for with_end_time."""
        return self.with_end_time(end)

    def can_merge_with(self, other: "StatusPeriod") -> bool:
        """Check if two periods can be merged."""
        if self._equipment_code != other._equipment_code:
            return False
        if self._status != other._status:
            return False
        return self._time_range.overlaps(other._time_range) or self._time_range.is_adjacent_to(other._time_range)

    def merge_with(self, other: "StatusPeriod") -> "StatusPeriod":
        """
        Merge two periods into one.

        Raises:
            StatusMergeError: If periods cannot be merged
        """
        if self._equipment_code != other._equipment_code:
            raise StatusMergeError.different_devices(
                self._equipment_code.value,
                other._equipment_code.value,
            )
        if self._status != other._status:
            raise StatusMergeError.different_statuses(
                self._status.name,
                other._status.name,
            )
        if not self.can_merge_with(other):
            raise StatusMergeError.non_adjacent()

        merged_range = self._time_range.union(other._time_range)
        return StatusPeriod(
            equipment_code=self._equipment_code,
            status=self._status,
            time_range=merged_range,
        )

    def duration_until(self, timestamp: datetime) -> float:
        """Get duration until a specific timestamp."""
        return self._time_range.duration_until(timestamp)

    # ========================================================================
    # Equality
    # ========================================================================

    def _get_equality_components(self) -> tuple:
        """Return components for equality comparison."""
        return (self._equipment_code, self._status, self._time_range)

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "equipment_code": str(self._equipment_code),
            "status": self._status.value,
            "status_name": self._status.name,
            "start": self._time_range.start.isoformat(),
            "end": self._time_range.end.isoformat() if self._time_range.end else None,
            "is_ongoing": self.is_ongoing,
            "duration_seconds": self.duration_seconds,
            "is_downtime": self.is_downtime,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusPeriod":
        """Deserialize from dictionary."""
        return cls.create(
            equipment_code=data["equipment_code"],
            status=data["status"],
            start=datetime.fromisoformat(data["start"]),
            end=(datetime.fromisoformat(data["end"]) if data.get("end") else None),
        )

    def __repr__(self) -> str:
        return f"StatusPeriod(" f"code={self._equipment_code.value!r}, " f"status={self._status.name!r}, " f"range={self._time_range!r})"


__all__ = ["StatusPeriod"]
