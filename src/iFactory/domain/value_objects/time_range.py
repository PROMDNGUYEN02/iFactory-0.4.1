# src/iFactory/domain/value_objects/time_range.py
"""
Time Range Value Object.

Represents a continuous time interval with optional end.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..common.value_object import ValueObject
from ..exceptions.domain_exceptions import InvalidTimeRangeError


class TimeRange(ValueObject):
    """
    Immutable value object representing a continuous time interval.

    Can represent:
    - Closed interval: Both start and end defined
    - Open interval: Start defined, end is None (ongoing)

    Usage:
        # Closed range
        range1 = TimeRange.between(start, end)

        # Open range (ongoing)
        range2 = TimeRange.starting_from(start)

        # Check containment
        if range1.contains(some_datetime):
            print("In range")

        # Check overlap
        if range1.overlaps(range2):
            print("Ranges overlap")
    """

    __slots__ = ("_start", "_end")

    def __init__(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> None:
        """
        Create TimeRange.

        Args:
            start: Start of the range
            end: End of the range (None for ongoing)

        Raises:
            InvalidTimeRangeError: If end is before start
        """
        if end is not None and start > end:
            raise InvalidTimeRangeError.end_before_start(start, end)
        self._start = start
        self._end = end

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def between(cls, start: datetime, end: datetime) -> "TimeRange":
        """Create closed time range."""
        return cls(start, end)

    @classmethod
    def starting_from(cls, start: datetime) -> "TimeRange":
        """Create open-ended time range (ongoing)."""
        return cls(start, None)

    @classmethod
    def for_duration(cls, start: datetime, duration: timedelta) -> "TimeRange":
        """Create range with specific duration."""
        return cls(start, start + duration)

    @classmethod
    def today(cls) -> "TimeRange":
        """Create range for today (00:00:00 to 23:59:59.999999)."""
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return cls(start, end)

    @classmethod
    def last_hours(cls, hours: int) -> "TimeRange":
        """Create range for last N hours until now."""
        now = datetime.now()
        return cls(now - timedelta(hours=hours), now)

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def start(self) -> datetime:
        """Start of the range."""
        return self._start

    @property
    def end(self) -> Optional[datetime]:
        """End of the range (None if ongoing)."""
        return self._end

    @property
    def is_ongoing(self) -> bool:
        """True if range has no end (open-ended)."""
        return self._end is None

    @property
    def is_closed(self) -> bool:
        """True if range has both start and end."""
        return self._end is not None

    @property
    def duration(self) -> Optional[timedelta]:
        """
        Duration of the range.

        Returns None if range is ongoing.
        """
        if self._end is None:
            return None
        return self._end - self._start

    @property
    def duration_seconds(self) -> float:
        """
        Duration in seconds.

        For ongoing ranges, calculates duration until now.
        """
        end = self._end or datetime.now()
        return (end - self._start).total_seconds()

    # ========================================================================
    # Methods
    # ========================================================================

    def duration_until(self, timestamp: datetime) -> float:
        """
        Calculate duration until a specific point in time.

        Pure method - doesn't use datetime.now().
        """
        end = self._end if self._end and self._end < timestamp else timestamp
        return (end - self._start).total_seconds()

    def contains(self, point: datetime) -> bool:
        """Check if a point in time falls within this range."""
        if point < self._start:
            return False
        if self._end is None:
            return True
        return point <= self._end

    def contains_range(self, other: "TimeRange") -> bool:
        """Check if this range completely contains another range."""
        if other._start < self._start:
            return False
        if self._end is None:
            return True
        if other._end is None:
            return False
        return other._end <= self._end

    def overlaps(self, other: "TimeRange") -> bool:
        """Check if two ranges overlap."""
        self_end = self._end or datetime.max
        other_end = other._end or datetime.max
        return self._start < other_end and other._start < self_end

    def is_adjacent_to(self, other: "TimeRange") -> bool:
        """Check if ranges are exactly adjacent (touch but don't overlap)."""
        return self._end == other._start or other._end == self._start

    def union(self, other: "TimeRange") -> "TimeRange":
        """
        Create union of two overlapping or adjacent ranges.

        Raises:
            InvalidTimeRangeError: If ranges are not contiguous
        """
        if not self.overlaps(other) and not self.is_adjacent_to(other):
            raise InvalidTimeRangeError.non_contiguous()

        new_start = min(self._start, other._start)

        if self._end is None or other._end is None:
            new_end = None
        else:
            new_end = max(self._end, other._end)

        return TimeRange(new_start, new_end)

    def intersection(self, other: "TimeRange") -> Optional["TimeRange"]:
        """
        Create intersection of two ranges.

        Returns None if ranges don't overlap.
        """
        if not self.overlaps(other):
            return None

        new_start = max(self._start, other._start)

        self_end = self._end or datetime.max
        other_end = other._end or datetime.max
        new_end_ts = min(self_end, other_end)

        new_end = None if new_end_ts == datetime.max else new_end_ts

        return TimeRange(new_start, new_end)

    def extend_to(self, new_end: datetime) -> "TimeRange":
        """Create new range with extended end."""
        if new_end < self._start:
            raise InvalidTimeRangeError.end_before_start(self._start, new_end)
        return TimeRange(self._start, new_end)

    def close_at(self, end: datetime) -> "TimeRange":
        """Close an ongoing range at specified time."""
        return self.extend_to(end)

    # ========================================================================
    # Equality
    # ========================================================================

    def _get_equality_components(self) -> tuple:
        """Return components for equality comparison."""
        return (self._start, self._end)

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "start": self._start.isoformat(),
            "end": self._end.isoformat() if self._end else None,
            "is_ongoing": self.is_ongoing,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeRange":
        """Deserialize from dictionary."""
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=(datetime.fromisoformat(data["end"]) if data.get("end") else None),
        )

    def __repr__(self) -> str:
        end_str = self._end.isoformat() if self._end else "ongoing"
        return f"TimeRange({self._start.isoformat()} -> {end_str})"

    def __str__(self) -> str:
        end_str = self._end.strftime("%H:%M:%S") if self._end else "..."
        return f"{self._start.strftime('%H:%M:%S')} - {end_str}"


__all__ = ["TimeRange"]
