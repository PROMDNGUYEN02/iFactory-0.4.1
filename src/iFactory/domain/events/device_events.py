from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..value_objects.status import Status


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for all domain events."""

    occurred_at: datetime
    event_type: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", self.__class__.__name__)


@dataclass(frozen=True, slots=True)
class StatusChangedEvent(DomainEvent):
    """Event emitted when a device successfully transitions to a new status."""

    equipment_code: str
    previous_status: Status
    new_status: Status
