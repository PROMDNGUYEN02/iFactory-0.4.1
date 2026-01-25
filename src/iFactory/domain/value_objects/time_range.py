from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from ..exceptions import InvalidTimeRangeError


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise InvalidTimeRangeError.end_before_start(self.start, self.end)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def overlaps(self, other: TimeRange) -> bool:
        return self.start < other.end and other.start < self.end

    def is_adjacent_to(self, other: TimeRange) -> bool:
        return self.end == other.start or other.end == self.start

    def intersection(self, other: TimeRange) -> Optional[TimeRange]:
        if not self.overlaps(other):
            return None
        return TimeRange(start=max(self.start, other.start), end=min(self.end, other.end))

    def union(self, other: TimeRange) -> TimeRange:
        if not self.overlaps(other) and not self.is_adjacent_to(other):
            raise InvalidTimeRangeError("Cannot union non-contiguous ranges")
        return TimeRange(start=min(self.start, other.start), end=max(self.end, other.end))
