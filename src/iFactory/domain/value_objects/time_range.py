from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from ..exceptions.time_exceptions import InvalidTimeRangeError


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Immutable value object đại diện cho một khoảng thời gian liên tục."""

    start: datetime
    end: Optional[datetime] = None  # [FIXED] Cho phép None để đại diện cho trạng thái đang diễn ra

    def __post_init__(self) -> None:
        # [FIXED] Chỉ kiểm tra logic nếu có thời gian kết thúc
        if self.end is not None and self.start > self.end:
            raise InvalidTimeRangeError.end_before_start(self.start, self.end)

    @property
    def duration_seconds(self) -> float:
        """Tính tổng số giây. Nếu đang diễn ra thì tính tới thời điểm hiện tại."""
        reference_end = self.end or datetime.now()
        return (reference_end - self.start).total_seconds()

    def overlaps(self, other: TimeRange) -> bool:
        # Xử lý so sánh với vô hạn (None)
        self_end = self.end or datetime.max
        other_end = other.end or datetime.max
        return self.start < other_end and other.start < self_end

    def is_adjacent_to(self, other: TimeRange) -> bool:
        return self.end == other.start or other.end == self.start

    def union(self, other: TimeRange) -> TimeRange:
        if not self.overlaps(other) and not self.is_adjacent_to(other):
            raise InvalidTimeRangeError.non_contiguous()
        # Union của một khoảng vô hạn vẫn là vô hạn
        new_end = None if (self.end is None or other.end is None) else max(self.end, other.end)
        return TimeRange(start=min(self.start, other.start), end=new_end)
