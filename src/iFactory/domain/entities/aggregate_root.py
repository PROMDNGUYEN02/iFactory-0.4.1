from __future__ import annotations

from typing import List

from ..events.base import DomainEvent


class AggregateRoot:
    """
    Base class for Domain Aggregates.

    Acts as a transaction boundary for state changes and captures Domain Events
    to be dispatched by the Unit of Work after successful persistence.
    """

    __slots__ = ("_domain_events",)

    def __init__(self) -> None:
        self._domain_events: List[DomainEvent] = []

    def _record_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def collect_events(self) -> List[DomainEvent]:
        events = self._domain_events[:]
        self._domain_events.clear()
        return events

    def clear_events(self) -> None:
        self._domain_events.clear()
