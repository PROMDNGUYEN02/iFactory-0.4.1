from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..exceptions.domain_exceptions import InvalidTimeRangeError


class TimeRange:
    """
    Immutable value object representing a continuous time interval.
    """

    __slots__ = ("_start", "_end")

    def __init__(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> None:
        if end is not None and start > end:
            raise InvalidTimeRangeError.end_before_start(start, end)
        self._start = start
        self._end = end

    @classmethod
    def between(cls, start: datetime, end: datetime) -> TimeRange:
        return cls(start, end)

    @classmethod
    def starting_from(cls, start: datetime) -> TimeRange:
        return cls(start, None)

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def end(self) -> Optional[datetime]:
        return self._end

    @property
    def is_ongoing(self) -> bool:
        return self._end is None

    @property
    def duration_seconds(self) -> float:
        # Note: If ongoing, we cannot calculate exact duration without a reference point.
        # But commonly we might want duration 'so far' or raise an error.
        # Here we assume duration is calculated up to 'now' if ongoing for convenience,
        # OR we could require the caller to handle None.
        # To keep it pure, we should probably NOT use datetime.now().
        # However, for property access, defaulting to None or raising might be better.
        # Given the previous implementation used datetime.now(), we'll stick to a
        # safe access pattern but strict purity would prefer passing a reference time.
        # For this refactor, we will only return duration if end is set,
        # or require the user to use a method `duration_until(timestamp)`.
        # However, to preserve API compatibility with the provided code:
        reference_end = self._end or datetime.now()
        return (reference_end - self._start).total_seconds()

    def duration_until(self, timestamp: datetime) -> float:
        """Pure method to calculate duration until a specific point in time."""
        end = self._end or timestamp
        return (end - self._start).total_seconds()

    def contains(self, point: datetime) -> bool:
        if point < self._start:
            return False
        if self._end is None:
            return True
        return point <= self._end

    def overlaps(self, other: TimeRange) -> bool:
        self_end = self._end or datetime.max
        other_end = other._end or datetime.max
        return self._start < other_end and other._start < self_end

    def is_adjacent_to(self, other: TimeRange) -> bool:
        # Exact touch
        return self._end == other._start or other._end == self._start

    def union(self, other: TimeRange) -> TimeRange:
        if not self.overlaps(other) and not self.is_adjacent_to(other):
            raise InvalidTimeRangeError.non_contiguous()

        new_start = min(self._start, other._start)

        if self._end is None or other._end is None:
            new_end = None
        else:
            new_end = max(self._end, other._end)

        return TimeRange(new_start, new_end)

    def intersection(self, other: TimeRange) -> Optional[TimeRange]:
        if not self.overlaps(other):
            return None

        new_start = max(self._start, other._start)

        self_end = self._end or datetime.max
        other_end = other._end or datetime.max

        new_end_ts = min(self_end, other_end)
        # If the intersection point is effectively infinite (both open ended), it's ongoing.
        # If one ends, the intersection ends.
        new_end = None if new_end_ts == datetime.max else new_end_ts

        return TimeRange(new_start, new_end)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimeRange):
            return NotImplemented
        return self._start == other._start and self._end == other._end

    def __hash__(self) -> int:
        return hash((self._start, self._end))

    def __repr__(self) -> str:
        end_str = self._end.isoformat() if self._end else "ongoing"
        return f"TimeRange({self._start.isoformat()} -> {end_str})"
