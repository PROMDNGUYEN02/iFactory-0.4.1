# File: src/iFactory/domain/value_objects/time_range.py
"""
Time Range Value Object - Validated time period.

Represents a duration between two points in time, ensuring
that start <= end. This object is immutable and provides
rich methods for calculating durations, overlaps, and set operations.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

from ..exceptions import InvalidTimeRangeError

__all__ = ["TimeRange"]


@dataclass(frozen=True, slots=True)
class TimeRange:
    """
    Immutable time range value object.

    This Value Object encapsulates a start and end datetime,
    enforcing the invariant that `start` must be less than or equal to `end`.

    Attributes:
        start: The inclusive start datetime of the period.
        end: The inclusive end datetime of the period.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """
        Validate that start time is not after end time.

        Raises:
            InvalidTimeRangeError: If start > end.
        """
        if self.start is None:
            raise InvalidTimeRangeError.null_boundary("start")
        if self.end is None:
            raise InvalidTimeRangeError.null_boundary("end")
        if self.start > self.end:
            raise InvalidTimeRangeError.end_before_start(self.start, self.end)

    @classmethod
    def from_datetimes(cls, start: datetime, end: datetime) -> "TimeRange":
        """
        Create a TimeRange from two datetime objects.

        Args:
            start: The start of the period.
            end: The end of the period.

        Returns:
            A TimeRange instance.
        """
        return cls(start, end)

    @classmethod
    def from_duration(cls, start: datetime, duration: timedelta) -> "TimeRange":
        """
        Create a TimeRange from a start time and duration.

        Args:
            start: The start timestamp.
            duration: The length of the period.

        Returns:
            A new TimeRange instance.

        Raises:
            InvalidTimeRangeError: If duration is negative.
        """
        if duration < timedelta(0):
            raise InvalidTimeRangeError.negative_duration(duration.total_seconds())
        return cls(start=start, end=start + duration)

    @classmethod
    def instant(cls, timestamp: datetime) -> "TimeRange":
        """
        Create a zero-duration TimeRange at a specific moment.

        Args:
            timestamp: The exact moment.

        Returns:
            A TimeRange where start equals end.
        """
        return cls(start=timestamp, end=timestamp)

    @classmethod
    def safe_create(
        cls, start: datetime, end: datetime, auto_swap: bool = False
    ) -> TimeRange | None:
        """
        Safely create a TimeRange, returning None if invalid.

        Args:
            start: The start datetime.
            end: The end datetime.
            auto_swap: If True, swap start/end when start > end.

        Returns:
            TimeRange if valid, None otherwise.
        """
        if start is None or end is None:
            return None
        if start > end:
            if auto_swap:
                (start, end) = (end, start)
            else:
                return None
        try:
            return cls(start, end)
        except InvalidTimeRangeError:
            return None

    @classmethod
    def from_timestamps(
        cls,
        start: datetime,
        end: datetime | None = None,
        default_duration_minutes: int = 1,
    ) -> "TimeRange":
        """
        Create from timestamps with fallback for missing end time.

        Args:
            start: Start datetime (required).
            end: End datetime (optional, defaults to start + duration).
            default_duration_minutes: Duration if end is None.

        Returns:
            A valid TimeRange.
        """
        if end is None:
            end = start + timedelta(minutes=default_duration_minutes)
        if start > end:
            (start, end) = (end, start)
        return cls(start, end)

    @classmethod
    def last_hours(cls, hours: int = 24) -> "TimeRange":
        """Create a range for the last N hours from now."""
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return cls(start, end)

    @classmethod
    def last_days(cls, days: int = 1) -> "TimeRange":
        """Create a range for the last N days from now."""
        end = datetime.now()
        start = end - timedelta(days=days)
        return cls(start, end)

    @classmethod
    def today(cls) -> "TimeRange":
        """Create a range for today (from midnight to now)."""
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start, now)

    @classmethod
    def for_date(cls, date: datetime) -> "TimeRange":
        """Create a range for the entire specific day."""
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return cls(start, end)

    @property
    def duration(self) -> timedelta:
        """Get the total duration of the period."""
        return self.end - self.start

    @property
    def duration_seconds(self) -> float:
        """Get the duration in seconds."""
        return self.duration.total_seconds()

    @property
    def duration_minutes(self) -> float:
        """Get the duration in minutes."""
        return self.duration_seconds / 60.0

    @property
    def duration_hours(self) -> float:
        """Get the duration in hours."""
        return self.duration_seconds / 3600.0

    @property
    def midpoint(self) -> datetime:
        """Calculate the exact midpoint of the time range."""
        return self.start + self.duration / 2

    @property
    def is_valid(self) -> bool:
        """Check if range is valid (start <= end)."""
        return self.start <= self.end

    @property
    def is_instant(self) -> bool:
        """Check if this is a zero-duration (instantaneous) range."""
        return self.start == self.end

    def contains(self, dt: datetime) -> bool:
        """
        Check if a specific datetime falls within this range.

        Args:
            dt: The datetime to check.

        Returns:
            True if `start <= dt <= end`.
        """
        return self.start <= dt <= self.end

    def contains_range(self, other: "TimeRange") -> bool:
        """
        Check if this range fully contains another range.

        Args:
            other: Another TimeRange.

        Returns:
            True if this range fully encompasses the other.
        """
        return self.start <= other.start and other.end <= self.end

    def overlaps(self, other: "TimeRange") -> bool:
        """
        Check if this range overlaps with another range.

        Args:
            other: Another TimeRange instance.

        Returns:
            True if intervals intersect.
        """
        return self.start <= other.end and other.start <= self.end

    def is_adjacent_to(self, other: "TimeRange") -> bool:
        """
        Check if this range is immediately adjacent to another.

        Two ranges are adjacent if one ends exactly when the other starts,
        with no gap between them.

        Args:
            other: Another TimeRange.

        Returns:
            True if one range ends exactly when the other starts.
        """
        return self.end == other.start or other.end == self.start

    def gap_to(self, other: "TimeRange") -> timedelta | None:
        """
        Calculate the gap between this range and another.

        Args:
            other: Another TimeRange.

        Returns:
            The duration of the gap, or None if ranges overlap or are adjacent.
        """
        if self.overlaps(other) or self.is_adjacent_to(other):
            return None
        if self.end < other.start:
            return other.start - self.end
        return self.start - other.end

    def intersection(self, other: "TimeRange") -> TimeRange | None:
        """
        Get the overlapping portion of two ranges.

        Args:
            other: Another TimeRange instance.

        Returns:
            A new TimeRange representing the overlap, or None if no overlap.
        """
        if not self.overlaps(other):
            return None
        return TimeRange(
            start=max(self.start, other.start), end=min(self.end, other.end)
        )

    def union(self, other: "TimeRange") -> "TimeRange":
        """
        Get a range covering both ranges (the convex hull).

        Args:
            other: Another TimeRange instance.

        Returns:
            A new TimeRange spanning from the earliest start to the latest end.
        """
        return TimeRange(
            start=min(self.start, other.start), end=max(self.end, other.end)
        )

    def split_at(self, dt: datetime) -> tuple["TimeRange", "TimeRange"] | None:
        """
        Split this range at a specific datetime.

        Args:
            dt: The datetime at which to split.

        Returns:
            A tuple of two TimeRanges, or None if dt is outside the range
            or at the boundaries.
        """
        if not self.contains(dt) or dt == self.start or dt == self.end:
            return None
        return (
            TimeRange(start=self.start, end=dt),
            TimeRange(start=dt, end=self.end),
        )

    def extend(
        self, before: timedelta | None = None, after: timedelta | None = None
    ) -> "TimeRange":
        """
        Extend the range by a specified amount before and/or after.

        Args:
            before: Optional duration to extend backwards from start.
            after: Optional duration to extend forwards from end.

        Returns:
            A new TimeRange with adjusted start/end times.
        """
        new_start = self.start - (before or timedelta())
        new_end = self.end + (after or timedelta())
        return TimeRange(new_start, new_end)

    def extend_start(self, delta: timedelta) -> "TimeRange":
        """Create a new range with the start extended earlier."""
        return TimeRange(start=self.start - delta, end=self.end)

    def extend_end(self, delta: timedelta) -> "TimeRange":
        """Create a new range with the end extended later."""
        return TimeRange(start=self.start, end=self.end + delta)

    def split_by_hours(self, hours: int = 1) -> Iterator["TimeRange"]:
        """
        Split the range into multiple chunks of a fixed hour duration.

        Args:
            hours: The duration of each chunk in hours.

        Yields:
            `TimeRange` instances covering the original range sequentially.
        """
        current = self.start
        delta = timedelta(hours=hours)
        while current < self.end:
            chunk_end = min(current + delta, self.end)
            yield TimeRange(current, chunk_end)
            current = chunk_end

    def iterate_days(self) -> Iterator[datetime]:
        """
        Iterate over each day (midnight) within this range.

        Yields:
            datetime objects at midnight for each day covered.
        """
        current = self.start.replace(hour=0, minute=0, second=0, microsecond=0)
        while current < self.end:
            yield current
            current += timedelta(days=1)

    def to_tuple(self) -> tuple[datetime, datetime]:
        """Convert to tuple (start, end)."""
        return (self.start, self.end)

    def format(self, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """Format the time range as a string."""
        return f"{self.start.strftime(fmt)} - {self.end.strftime(fmt)}"

    def to_dict(self) -> dict[str, str]:
        """Convert the range to a dictionary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_seconds": str(self.duration_seconds),
        }

    def __str__(self) -> str:
        """String representation uses default formatting."""
        return self.format()

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"TimeRange(start={self.start!r}, end={self.end!r})"

    def __lt__(self, other: "TimeRange") -> bool:
        """Enable sorting by start time, then by end time."""
        if isinstance(other, TimeRange):
            if self.start != other.start:
                return self.start < other.start
            return self.end < other.end
        return NotImplemented
