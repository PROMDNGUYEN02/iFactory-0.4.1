from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from .equipment_code import EquipmentCode
from .time_range import TimeRange
from ..enums.machine_status import MachineStatus
from ..exceptions.time_exceptions import StatusMergeError


@dataclass(frozen=True, slots=True)
class StatusPeriod:
    """
    A continuous period where a specific device was in a specific state.
    Used for machine history and production reporting.
    """

    equipment_code: EquipmentCode
    status: MachineStatus
    time_range: TimeRange

    @classmethod
    def create(cls, code: str, raw_status: str, start: datetime, end: datetime) -> StatusPeriod:
        return cls(equipment_code=EquipmentCode(code), status=MachineStatus.from_business_term(raw_status), time_range=TimeRange(start, end))

    def is_mergeable_with(self, other: StatusPeriod) -> bool:
        """Business rule: Two periods can merge if they are the same device, same state, and touch in time."""
        if self.equipment_code != other.equipment_code or self.status != other.status:
            return False
        return self.time_range.overlaps(other.time_range) or self.time_range.is_adjacent_to(other.time_range)

    def merge_with(self, other: StatusPeriod) -> StatusPeriod:
        """Combines two periods if business rules allow."""
        if self.equipment_code != other.equipment_code:
            raise StatusMergeError.different_devices(self.equipment_code.value, other.equipment_code.value)
        if self.status != other.status:
            raise StatusMergeError.different_statuses(self.status.value, other.status.value)
        if not self.is_mergeable_with(other):
            raise StatusMergeError.non_adjacent()

        return StatusPeriod(equipment_code=self.equipment_code, status=self.status, time_range=self.time_range.union(other.time_range))
