from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status
from ..events.device_events import StatusChangedEvent


@dataclass(slots=True)
class Device:
    """Aggregate Root representing a manufacturing device."""

    equipment_code: EquipmentCode
    current_status: Status = field(default_factory=Status.unknown)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    # Internal list of state-change events
    _events: List[StatusChangedEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(cls, code: str, raw_status: str | None = None, name: str | None = None, last_update: datetime | None = None) -> Device:
        """Factory method to reconstruct or create a Device entity."""
        return cls(equipment_code=EquipmentCode(code), current_status=Status.from_raw(raw_status), name=name, last_update=last_update)

    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def is_operational(self) -> bool:
        return self.current_status.is_running

    def update_status(self, raw_status: str, update_time: datetime | None = None) -> bool:
        """
        Business policy: Update the device status.
        Ignores idempotent updates. Generates Domain Events.
        """
        new_status = Status.from_raw(raw_status)

        if self.current_status == new_status:
            return False

        ts = update_time or datetime.now()

        event = StatusChangedEvent(
            equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=new_status, occurred_at=ts
        )
        self._events.append(event)

        self.current_status = new_status
        self.last_update = ts
        return True

    def collect_events(self) -> List[StatusChangedEvent]:
        """Atomically extracts and clears the uncommitted domain events."""
        events = self._events[:]
        self._events.clear()
        return events
