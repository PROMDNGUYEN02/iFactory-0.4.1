from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..enums.device_status import DeviceStatus
from ..exceptions import HistoryMergeError
from .equipment_code import EquipmentCode
from .status import Status
from .time_range import TimeRange


@dataclass(frozen=True, slots=True)
class DeviceHistory:
    equipment_code: EquipmentCode
    status: Status
    time_range: TimeRange

    @classmethod
    def create(cls, code: str, status: str | DeviceStatus, start: datetime, end: datetime) -> "DeviceHistory":
        status_vo = Status(status) if isinstance(status, DeviceStatus) else Status(DeviceStatus.from_code_or_name(status))
        return cls(
            equipment_code=EquipmentCode(code),
            status=status_vo,
            time_range=TimeRange(start, end),
        )

    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def duration_seconds(self) -> float:
        return self.time_range.duration_seconds

    def overlaps(self, other: "DeviceHistory") -> bool:
        return self.time_range.overlaps(other.time_range)

    def is_adjacent_to(self, other: "DeviceHistory") -> bool:
        return self.time_range.is_adjacent_to(other.time_range)

    def merge_with(self, other: "DeviceHistory") -> "DeviceHistory":
        if self.equipment_code != other.equipment_code:
            raise HistoryMergeError.different_devices(self.code, other.code)

        if self.status != other.status:
            raise HistoryMergeError.different_statuses(self.status.name, other.status.name)

        if not self.overlaps(other) and not self.is_adjacent_to(other):
            raise HistoryMergeError("Cannot merge non-adjacent periods.")

        return DeviceHistory(
            equipment_code=self.equipment_code,
            status=self.status,
            time_range=self.time_range.union(other.time_range),
        )

    def truncate_to(self, time_range: TimeRange) -> Optional["DeviceHistory"]:
        intersection = self.time_range.intersection(time_range)
        if intersection is None:
            return None

        return DeviceHistory(
            equipment_code=self.equipment_code,
            status=self.status,
            time_range=intersection,
        )

    def __lt__(self, other: "DeviceHistory") -> bool:
        if not isinstance(other, DeviceHistory):
            return NotImplemented
        if self.equipment_code != other.equipment_code:
            return self.equipment_code.value < other.equipment_code.value
        return self.time_range < other.time_range
