from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for all domain events indicating that something of business interest occurred."""

    occurred_at: datetime
    event_type: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", self.__class__.__name__)
