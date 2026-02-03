# File: domain/common/aggregate.py
from __future__ import annotations

from typing import List, TYPE_CHECKING

from .event import DomainEvent

if TYPE_CHECKING:
    from .event_dispatcher import IEventDispatcher


class AggregateRoot:
    """
    Base class for Domain Aggregates.

    Acts as a transaction boundary for state changes and captures Domain Events
    to be dispatched by the Application Layer after successful persistence.

    Usage:
        # In domain entity
        self._record_event(StatusChangedEvent(...))

        # In application layer (after commit)
        events = aggregate.collect_events()
        await event_dispatcher.dispatch_all(events)
    """

    __slots__ = ("_domain_events",)

    def __init__(self) -> None:
        self._domain_events: List[DomainEvent] = []

    def _record_event(self, event: DomainEvent) -> None:
        """Records a domain event that occurred within this aggregate."""
        self._domain_events.append(event)

    def collect_events(self) -> List[DomainEvent]:
        """
        Returns and clears all recorded domain events.

        Call this AFTER successful persistence to get events
        ready for dispatching.
        """
        events = self._domain_events[:]
        self._domain_events.clear()
        return events

    def peek_events(self) -> List[DomainEvent]:
        """
        Returns events WITHOUT clearing them.

        Useful for inspection/testing without consuming events.
        """
        return self._domain_events[:]

    def clear_events(self) -> None:
        """Clears pending events without returning them."""
        self._domain_events.clear()

    @property
    def has_pending_events(self) -> bool:
        """Check if there are pending events."""
        return len(self._domain_events) > 0


__all__ = ["AggregateRoot"]
