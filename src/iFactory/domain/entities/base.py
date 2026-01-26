from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from ..events.base import DomainEvent


@dataclass(slots=True)
class AggregateRoot:
    """
    Base class for Domain Aggregates.
    Manages the collection and dispatching of Domain Events to preserve invariants.
    """

    _events: List[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def _add_event(self, event: DomainEvent) -> None:
        """Registers a domain event internally for later dispatch."""
        self._events.append(event)

    def collect_events(self) -> List[DomainEvent]:
        """Atomically extracts and clears the uncommitted domain events."""
        events = self._events[:]
        self._events.clear()
        return events
