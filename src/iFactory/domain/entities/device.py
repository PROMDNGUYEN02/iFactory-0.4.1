from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .base import AggregateRoot
from ..value_objects.equipment_code import EquipmentCode
from ..enums.machine_status import MachineStatus
from ..events.device_events import StatusChangedEvent
from ..policies.status_transition_policy import StatusTransitionPolicy


@dataclass(slots=True)
class Device(AggregateRoot):
    """
    Aggregate Root representing a manufacturing device.
    Responsible for maintaining business invariants regarding device lifecycle and status state.
    """

    equipment_code: EquipmentCode
    current_status: MachineStatus = field(default=MachineStatus.UNKNOWN)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def create(cls, code: str, raw_status: Optional[str] = None, name: Optional[str] = None) -> Device:
        """Factory method to reconstitute a Device aggregate from primitive inputs."""
        return cls(
            equipment_code=EquipmentCode(code), current_status=MachineStatus.from_business_term(raw_status), name=name, last_update=datetime.now()
        )

    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def is_operational(self) -> bool:
        return self.current_status.is_running

    def update_status(self, raw_status: str, update_time: Optional[datetime] = None) -> bool:
        """
        Business behavior: Updates the device status.
        Ignores idempotent updates. Validates transitions. Generates Domain Events.
        """
        new_status = MachineStatus.from_business_term(raw_status)

        if self.current_status == new_status:
            return False

        # Validate transition against business rules
        StatusTransitionPolicy.validate(self.current_status, new_status)

        ts = update_time or datetime.now()

        # Generate the event
        event = StatusChangedEvent(
            occurred_at=ts, equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=new_status
        )
        self._add_event(event)

        # Mutate the internal state
        self.current_status = new_status
        self.last_update = ts
        return True
