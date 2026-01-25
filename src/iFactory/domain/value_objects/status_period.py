from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .equipment_code import EquipmentCode
from .status import Status
from .time_range import TimeRange
from ..exceptions import StatusMergeError


@dataclass(frozen=True, slots=True)
class StatusPeriod:
    equipment_code: EquipmentCode
    status: Status
    time_range: TimeRange

    @property
    def duration_seconds(self) -> float:
        return self.time_range.duration_seconds

    def merge_with(self, other: StatusPeriod) -> StatusPeriod:
        if self.equipment_code != other.equipment_code:
            raise StatusMergeError("Cannot merge different devices")
        if self.status != other.status:
            raise StatusMergeError("Cannot merge different statuses")

        return StatusPeriod(equipment_code=self.equipment_code, status=self.status, time_range=self.time_range.union(other.time_range))

    def truncate(self, window: TimeRange) -> Optional[StatusPeriod]:
        intersection = self.time_range.intersection(window)
        if not intersection:
            return None
        return StatusPeriod(self.equipment_code, self.status, intersection)


DeviceHistory = StatusPeriod
