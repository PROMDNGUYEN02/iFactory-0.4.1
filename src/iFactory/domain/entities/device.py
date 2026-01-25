from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Union
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status
from ..events.device_status_changed import StatusChangedEvent
from ..enums.device_status import DeviceStatus


@dataclass(slots=True)
class Device:
    equipment_code: EquipmentCode
    current_status: Status = field(default_factory=Status.unknown)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None
    _events: List[StatusChangedEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(cls, code: str, status: str = "unknown", name: str | None = None, last_update: datetime | None = None) -> Device:
        """Khởi tạo thiết bị với đầy đủ thông tin trạng thái và thời gian."""
        return cls(
            equipment_code=EquipmentCode(code), current_status=Status(DeviceStatus.from_code_or_name(status)), name=name, last_update=last_update
        )

    def update_status(self, new_status: Union[Status, DeviceStatus, str], update_time: datetime | None = None) -> bool:
        if isinstance(new_status, str):
            ns = Status(DeviceStatus.from_code_or_name(new_status))
        elif isinstance(new_status, DeviceStatus):
            ns = Status(new_status)
        else:
            ns = new_status

        if self.current_status == ns:
            return False

        ts = update_time or datetime.now()
        event = StatusChangedEvent(equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=ns, occurred_at=ts)
        self._events.append(event)
        self.current_status = ns
        self.last_update = ts
        return True

    def collect_events(self) -> List[StatusChangedEvent]:
        events = self._events[:]
        self._events.clear()
        return events

    @property
    def code(self) -> str:
        return self.equipment_code.value
