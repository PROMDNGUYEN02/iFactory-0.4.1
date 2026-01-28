from __future__ import annotations

from datetime import datetime

from .equipment_code import EquipmentCode
from .time_range import TimeRange
from ..enums.machine_status import MachineStatus
from ..exceptions.domain_exceptions import StatusMergeError


class StatusPeriod:
    """
    Immutable Value Object representing a continuous period during which
    a device maintained a specific status.
    """

    __slots__ = (
        "_equipment_code",
        "_status",
        "_time_range",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        status: MachineStatus,
        time_range: TimeRange,
    ) -> None:
        self._equipment_code = equipment_code
        self._status = status
        self._time_range = time_range

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
    def duration_seconds(self) -> float:
        return self._time_range.duration_seconds

    def with_end_time(self, end: datetime) -> StatusPeriod:
        safe_end = max(end, self._time_range.start)
        return StatusPeriod(
            equipment_code=self._equipment_code,
            status=self._status,
            time_range=TimeRange(self._time_range.start, safe_end),
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StatusPeriod):
            return NotImplemented
        return self._equipment_code == other._equipment_code and self._status == other._status and self._time_range == other._time_range

    def __hash__(self) -> int:
        return hash((self._equipment_code, self._status, self._time_range))

    def __repr__(self) -> str:
        return f"StatusPeriod(code={self._equipment_code.value!r}, status={self._status.name!r}, range={self._time_range!r})"
