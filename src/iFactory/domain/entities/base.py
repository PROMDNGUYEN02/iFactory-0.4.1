from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from ..events.base import DomainEvent


@dataclass
class AggregateRoot:
    """
    Base class for Domain Aggregates.
    Acts as a transaction boundary for state changes and captures Domain Events
    to be dispatched by the Unit of Work.
    """

    _domain_events: List[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def _record_event(self, event: DomainEvent) -> None:
        """Registers a domain event internally for later dispatch."""
        self._domain_events.append(event)

    def collect_events(self) -> List[DomainEvent]:
        """Atomically extracts and clears the uncommitted domain events."""
        events = self._domain_events[:]
        self._domain_events.clear()
        return events
