from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..enums.device_status import DeviceStatus
from ..events.device_status_changed import StatusChangedEvent
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status


@dataclass(slots=True)
class Device:
    equipment_code: EquipmentCode
    current_status: Status = field(default_factory=Status.unknown)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    _events: List[StatusChangedEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        code: str | EquipmentCode,
        status: str | DeviceStatus | Status,
        last_update: datetime | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> "Device":
        ec = code if isinstance(code, EquipmentCode) else EquipmentCode(code)

        if isinstance(status, Status):
            s = status
        elif isinstance(status, DeviceStatus):
            s = Status(status)
        else:
            s = Status(DeviceStatus.from_code_or_name(status))

        return cls(
            equipment_code=ec,
            current_status=s,
            last_update=last_update,
            name=name,
            description=description,
        )

    def update_status(self, new_status: Status | DeviceStatus | str, update_time: datetime | None = None) -> bool:
        if isinstance(new_status, str):
            new_status = Status(DeviceStatus.from_code_or_name(new_status))
        elif isinstance(new_status, DeviceStatus):
            new_status = Status(new_status)

        if self.current_status == new_status:
            return False

        update_ts = update_time or datetime.now()

        event = StatusChangedEvent(
            equipment_code=self.code,
            previous_status=self.current_status,
            new_status=new_status,
            occurred_at=update_ts,
        )
        self._events.append(event)

        object.__setattr__(self, "current_status", new_status)
        object.__setattr__(self, "last_update", update_ts)
        return True

    def get_events(self) -> List[StatusChangedEvent]:
        events = self._events.copy()
        self._events.clear()
        return events

    def has_uncommitted_events(self) -> bool:
        return len(self._events) > 0

    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def is_running(self) -> bool:
        return self.current_status.is_running

    @property
    def requires_attention(self) -> bool:
        return self.current_status.requires_attention

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Device):
            return False
        return self.equipment_code == other.equipment_code

    def __hash__(self) -> int:
        return hash(self.equipment_code)
