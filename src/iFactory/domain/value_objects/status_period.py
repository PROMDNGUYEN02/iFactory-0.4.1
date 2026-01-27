from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .equipment_code import EquipmentCode
from .time_range import TimeRange
from ..enums.machine_status import MachineStatus


@dataclass(slots=True)
class StatusPeriod:
    equipment_code: EquipmentCode
    status: MachineStatus
    time_range: TimeRange
    id: Optional[str] = None

    @classmethod
    def create(cls, code: str, raw_status: str, start: datetime, end: Optional[datetime] = None, id: Optional[str] = None) -> StatusPeriod:
        # [FIXED] Đồng bộ tham số để Command gọi không bị lỗi NoneType
        return cls(id=id, equipment_code=EquipmentCode(code), status=MachineStatus.from_business_term(raw_status), time_range=TimeRange(start, end))

    @property
    def device_code(self) -> str:
        return self.equipment_code.value

    @property
    def status_code(self) -> str:
        return str(self.status.value)

    @property
    def start_time(self) -> datetime:
        return self.time_range.start

    @property
    def end_time(self) -> Optional[datetime]:
        return self.time_range.end

    @end_time.setter
    def end_time(self, value: datetime):
        # [FIXED] Cập nhật end_time bằng cách tạo mới TimeRange một cách an toàn
        # Đảm bảo end_time mới không nhỏ hơn start_time
        safe_end = max(value, self.start_time)
        self.time_range = TimeRange(self.start_time, safe_end)
