from __future__ import annotations
from dataclasses import dataclass

from .base import DomainEvent
from ..enums.machine_status import MachineStatus


@dataclass(frozen=True, slots=True)
class StatusChangedEvent(DomainEvent):
    """Event emitted when a device successfully transitions to a new business status."""

    equipment_code: str
    previous_status: MachineStatus
    new_status: MachineStatus
