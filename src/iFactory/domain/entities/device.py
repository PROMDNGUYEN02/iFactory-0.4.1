from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status
from ..events import StatusChangedEvent
from ..policies.status_transition_policy import StatusTransitionPolicy


@dataclass(slots=True)
class Device:
    """
    Aggregate Root representing a manufacturing device.
    Responsible for maintaining business invariants regarding device state.
    """

    equipment_code: EquipmentCode
    current_status: Status = field(default_factory=Status.unknown)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    _events: List[StatusChangedEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(cls, code: str, raw_status: Optional[str] = None, name: Optional[str] = None) -> Device:
        """Factory method to reconstitute a Device aggregate."""
        return cls(equipment_code=EquipmentCode(code), current_status=Status.from_raw(raw_status), name=name, last_update=datetime.now())

    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def is_operational(self) -> bool:
        return self.current_status.is_running

    def update_status(self, raw_status: str, update_time: Optional[datetime] = None) -> bool:
        """
        Business policy: Updates the device status.
        Ignores idempotent updates. Validates transitions. Generates Domain Events.
        """
        new_status = Status.from_raw(raw_status)

        if self.current_status == new_status:
            return False

        # Apply business transition rules
        StatusTransitionPolicy.validate(self.current_status, new_status)

        ts = update_time or datetime.now()

        event = StatusChangedEvent(
            occurred_at=ts, equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=new_status
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
