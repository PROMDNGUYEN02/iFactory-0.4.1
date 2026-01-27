from __future__ import annotations

from datetime import datetime


class DomainEvent:
    """
    Base class for all domain events.
    Immutable records of business facts.
    """

    __slots__ = ("_occurred_at", "_event_type")

    def __init__(self, occurred_at: datetime) -> None:
        self._occurred_at = occurred_at
        self._event_type = self.__class__.__name__

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at

    @property
    def event_type(self) -> str:
        return self._event_type

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DomainEvent):
            return NotImplemented
        return self._event_type == other._event_type and self._occurred_at == other._occurred_at

    def __hash__(self) -> int:
        return hash((self._event_type, self._occurred_at))
