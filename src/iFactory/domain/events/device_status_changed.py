"""
Domain Events Package.

Contains domain events emitted by entities when state changes.
These events are used by event listeners for logging, notifications, and audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = ["StatusChangedEvent", "DomainEvent"]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """
    Base class for all domain events.

    All domain events inherit from this class.
    Events are immutable (frozen) and use slots for memory efficiency.
    """

    event_type: str = field(init=False, repr=False)
    """Event type identifier (auto-populated from class name)."""

    occurred_at: datetime
    """Timestamp when the event occurred."""

    def __post_init__(self) -> None:
        """Auto-populate event_type from class name."""
        object.__setattr__(
            self,
            "event_type",
            self.__class__.__name__,
        )


@dataclass(frozen=True, slots=True)
class StatusChangedEvent(DomainEvent):
    """
    Domain Event: Device status changed.

    Emitted when a device's status transitions from one state to another.
    Used by:
        - Event listeners (logging, notifications)
        - Audit trails
        - External system integrations

    Business Rule: Only emitted when status actually changes.
    """

    equipment_code: str
    """The unique identifier for the equipment."""

    previous_status: "Status"
    """The status before the change."""

    new_status: "Status"
    """The status after the change."""

    def __post_init__(self) -> None:
        """Initialize base class."""
        super().__post_init__()
