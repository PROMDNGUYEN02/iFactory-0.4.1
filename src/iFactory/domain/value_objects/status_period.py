from __future__ import annotations

from datetime import datetime
from typing import Optional

from .equipment_code import EquipmentCode
from .time_range import TimeRange
from ..enums.machine_status import MachineStatus
from ..exceptions.time_exceptions import StatusMergeError


class StatusPeriod:
    """
    Represents a continuous period during which a device maintained a specific status.

    Used for historical analysis and timeline generation.
    """

    __slots__ = (
        "_id",
        "_equipment_code",
        "_status",
        "_time_range",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        status: MachineStatus,
        time_range: TimeRange,
        id: Optional[str] = None,
    ) -> None:
        self._id = id
        self._equipment_code = equipment_code
        self._status = status
        self._time_range = time_range

    @classmethod
    def create(
        cls,
        code: str,
        raw_status: str | int,
        start: datetime,
        end: Optional[datetime] = None,
        id: Optional[str] = None,
    ) -> StatusPeriod:
        return cls(
            id=id,
            equipment_code=EquipmentCode(code),
            status=MachineStatus.from_raw_value(raw_status),
            time_range=TimeRange(start, end),
        )

    @classmethod
    def ongoing(
        cls,
        code: str,
        raw_status: str | int,
        start: datetime,
    ) -> StatusPeriod:
        return cls.create(code, raw_status, start, None)

    @property
    def id(self) -> Optional[str]:
        return self._id

    @property
    def equipment_code(self) -> EquipmentCode:
        return self._equipment_code

    @property
    def status(self) -> MachineStatus:
        return self._status

    @property
    def time_range(self) -> TimeRange:
        return self._time_range

    @property
    def device_code(self) -> str:
        return self._equipment_code.value

    @property
    def status_code(self) -> int:
        return self._status.value

    @property
    def status_name(self) -> str:
        return self._status.display_name

    @property
    def start_time(self) -> datetime:
        return self._time_range.start

    @property
    def end_time(self) -> Optional[datetime]:
        return self._time_range.end

    @property
    def is_ongoing(self) -> bool:
        return self._time_range.end is None

    @property
    def duration_seconds(self) -> float:
        return self._time_range.duration_seconds

    def with_end_time(self, end: datetime) -> StatusPeriod:
        safe_end = max(end, self.start_time)
        return StatusPeriod(
            id=self._id,
            equipment_code=self._equipment_code,
            status=self._status,
            time_range=TimeRange(self.start_time, safe_end),
        )

    def can_merge_with(self, other: StatusPeriod) -> bool:
        if self._equipment_code != other._equipment_code:
            return False
        if self._status != other._status:
            return False
        return self._time_range.overlaps(other._time_range) or self._time_range.is_adjacent_to(other._time_range)

    def merge_with(self, other: StatusPeriod) -> StatusPeriod:
        if self._equipment_code != other._equipment_code:
            raise StatusMergeError.different_devices(
                self.device_code,
                other.device_code,
            )
        if self._status != other._status:
            raise StatusMergeError.different_statuses(
                self.status_name,
                other.status_name,
            )
        if not self.can_merge_with(other):
            raise StatusMergeError.non_adjacent()

        merged_range = self._time_range.union(other._time_range)
        return StatusPeriod(
            id=self._id,
            equipment_code=self._equipment_code,
            status=self._status,
            time_range=merged_range,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StatusPeriod):
            return NotImplemented
        return self._equipment_code == other._equipment_code and self._status == other._status and self._time_range == other._time_range

    def __hash__(self) -> int:
        return hash((self._equipment_code, self._status, self._time_range))

    def __repr__(self) -> str:
        return f"StatusPeriod(code={self.device_code!r}, " f"status={self.status_name!r}, " f"range={self._time_range!r})"
