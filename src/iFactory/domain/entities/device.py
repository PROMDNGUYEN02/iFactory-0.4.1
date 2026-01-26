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
    Aggregate Root representing a distinct manufacturing device on the shop floor.
    Ensures business invariants regarding equipment state transitions.
    """

    equipment_code: EquipmentCode
    current_status: MachineStatus = field(default=MachineStatus.UNKNOWN)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def register_new(cls, code: str, name: Optional[str] = None) -> Device:
        """Factory method to register a new device in the domain."""
        return cls(equipment_code=EquipmentCode(code), name=name, current_status=MachineStatus.UNKNOWN, last_update=datetime.now())

    @property
    def is_operational(self) -> bool:
        """Domain query: checks if the device is currently producing."""
        return self.current_status.is_running

    def start_production(self, timestamp: datetime) -> None:
        """Domain behavior: Operator or system initiates production."""
        self._transition_to(MachineStatus.RUNNING, timestamp)

    def trigger_alarm(self, timestamp: datetime) -> None:
        """Domain behavior: Machine faults or safety systems triggered."""
        self._transition_to(MachineStatus.ALARM, timestamp)

    def begin_maintenance(self, timestamp: datetime) -> None:
        """Domain behavior: Machine enters scheduled or reactive maintenance."""
        self._transition_to(MachineStatus.MAINTENANCE, timestamp)

    def shutdown(self, timestamp: datetime) -> None:
        """Domain behavior: Machine powered down completely."""
        self._transition_to(MachineStatus.SHUTDOWN, timestamp)

    def stop_operation(self, timestamp: datetime) -> None:
        """Domain behavior: Machine halted but powered on (idle)."""
        self._transition_to(MachineStatus.STOPPED, timestamp)

    def report_sensor_status(self, raw_status: str, timestamp: datetime) -> None:
        """Domain behavior: Inbound telemetry update from physical hardware."""
        new_status = MachineStatus.from_business_term(raw_status)
        self._transition_to(new_status, timestamp)

    def _transition_to(self, new_status: MachineStatus, timestamp: datetime) -> None:
        """Internal state mutation enforcing business policies."""
        if self.current_status == new_status:
            return

        StatusTransitionPolicy.validate(self.current_status, new_status)

        event = StatusChangedEvent(
            occurred_at=timestamp, equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=new_status
        )
        self._record_event(event)

        self.current_status = new_status
        self.last_update = timestamp
