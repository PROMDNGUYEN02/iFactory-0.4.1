# src/iFactory/domain/common/event.py
"""
Domain Events with versioning, correlation, and metadata support.

Features:
- Event versioning for schema evolution
- Correlation/Causation IDs for tracing
- Rich metadata support
- Serialization helpers
- Compatible with both class-based and dataclass events
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Type, TypeVar

E = TypeVar("E", bound="DomainEvent")


@dataclass(frozen=True, slots=True)
class EventMetadata:
    """
    Metadata for domain events.

    Provides context for event processing, tracing, and auditing.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def with_correlation(self, correlation_id: str) -> "EventMetadata":
        """Create new metadata with correlation ID."""
        return EventMetadata(
            event_id=self.event_id,
            correlation_id=correlation_id,
            causation_id=self.causation_id,
            user_id=self.user_id,
            source=self.source,
            timestamp=self.timestamp,
        )

    def with_causation(self, causation_id: str) -> "EventMetadata":
        """Create new metadata linking to causing event."""
        return EventMetadata(
            event_id=self.event_id,
            correlation_id=self.correlation_id,
            causation_id=causation_id,
            user_id=self.user_id,
            source=self.source,
            timestamp=self.timestamp,
        )

    def derive(self, new_event_id: Optional[str] = None) -> "EventMetadata":
        """
        Derive new metadata from this one (for caused events).
        Links causation to this event and inherits correlation.
        """
        return EventMetadata(
            event_id=new_event_id or str(uuid.uuid4()),
            correlation_id=self.correlation_id,
            causation_id=self.event_id,  # This event caused the new one
            user_id=self.user_id,
            source=self.source,
            timestamp=datetime.now(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMetadata":
        """Create from dictionary."""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            user_id=data.get("user_id"),
            source=data.get("source"),
            timestamp=(datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now()),
        )


class DomainEvent(ABC):
    """
    Base class for all domain events.

    Domain events are immutable facts about something that happened
    in the domain. They are named in past tense (e.g., OrderPlaced,
    PaymentReceived).

    Features:
    - Versioning for schema evolution
    - Correlation/causation tracking
    - Rich metadata
    - Serialization support

    Usage (class-based):
        class OrderPlaced(DomainEvent):
            VERSION: ClassVar[int] = 1

            def __init__(
                self,
                order_id: str,
                customer_id: str,
                occurred_at: Optional[datetime] = None,
            ):
                super().__init__(occurred_at=occurred_at)
                self._order_id = order_id
                self._customer_id = customer_id

            @property
            def order_id(self) -> str:
                return self._order_id

            def to_dict(self) -> Dict[str, Any]:
                data = super().to_dict()
                data["order_id"] = self._order_id
                data["customer_id"] = self._customer_id
                return data

    Usage (dataclass - recommended for simple events):
        @dataclass(frozen=True)
        class OrderPlaced(DomainEvent):
            order_id: str
            customer_id: str
            # Note: Must call super().__init__() in __post_init__
    """

    # Class-level version for schema evolution
    VERSION: ClassVar[int] = 1

    __slots__ = ("_occurred_at", "_event_type", "_version", "_metadata")

    def __init__(
        self,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        object.__setattr__(self, "_occurred_at", occurred_at or datetime.now())
        object.__setattr__(self, "_event_type", self.__class__.__name__)
        object.__setattr__(self, "_version", self.__class__.VERSION)
        object.__setattr__(self, "_metadata", metadata or EventMetadata())

    @property
    def occurred_at(self) -> datetime:
        """When the event occurred."""
        return self._occurred_at

    @property
    def event_type(self) -> str:
        """Event type name (class name)."""
        return self._event_type

    @property
    def version(self) -> int:
        """Event schema version."""
        return self._version

    @property
    def metadata(self) -> EventMetadata:
        """Event metadata."""
        return self._metadata

    @property
    def event_id(self) -> str:
        """Unique event identifier."""
        return self._metadata.event_id

    @property
    def correlation_id(self) -> Optional[str]:
        """Correlation ID for tracing."""
        return self._metadata.correlation_id

    @property
    def causation_id(self) -> Optional[str]:
        """ID of event that caused this one."""
        return self._metadata.causation_id

    def with_metadata(self: E, metadata: EventMetadata) -> E:
        """
        Create a copy with new metadata.

        Note: Subclasses with additional fields should override this.
        """
        new_event = object.__new__(self.__class__)
        object.__setattr__(new_event, "_occurred_at", self._occurred_at)
        object.__setattr__(new_event, "_event_type", self._event_type)
        object.__setattr__(new_event, "_version", self._version)
        object.__setattr__(new_event, "_metadata", metadata)

        # Copy any additional slots from subclass
        for slot in self._get_subclass_slots():
            if hasattr(self, slot):
                object.__setattr__(new_event, slot, getattr(self, slot))

        return new_event

    def _get_subclass_slots(self) -> tuple:
        """Get slots defined in subclasses (not in DomainEvent)."""
        base_slots = set(DomainEvent.__slots__)
        all_slots = set()
        for cls in type(self).__mro__:
            if hasattr(cls, "__slots__"):
                all_slots.update(cls.__slots__)
        return tuple(all_slots - base_slots)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize event to dictionary.

        Subclasses should override and call super().to_dict().
        """
        return {
            "event_type": self._event_type,
            "version": self._version,
            "occurred_at": self._occurred_at.isoformat(),
            "metadata": self._metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls: Type[E], data: Dict[str, Any]) -> E:
        """
        Deserialize event from dictionary.

        Subclasses must override for proper deserialization.
        """
        raise NotImplementedError(f"{cls.__name__} must implement from_dict for deserialization")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DomainEvent):
            return NotImplemented
        return self._metadata.event_id == other._metadata.event_id

    def __hash__(self) -> int:
        return hash(self._metadata.event_id)

    def __repr__(self) -> str:
        return f"{self._event_type}(" f"id={self._metadata.event_id[:8]}..., " f"at={self._occurred_at.isoformat()}, " f"v={self._version})"


# ============================================================================
# Event Envelope (for transport/storage)
# ============================================================================


@dataclass(frozen=True)
class EventEnvelope:
    """
    Envelope wrapping domain events for transport/storage.

    Provides:
    - Aggregate context (type, ID, version)
    - Sequence number for ordering
    - Serialized payload
    """

    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    sequence_number: int
    event_type: str
    event_version: int
    event_data: Dict[str, Any]
    metadata: EventMetadata

    def to_dict(self) -> Dict[str, Any]:
        """Serialize envelope."""
        return {
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "sequence_number": self.sequence_number,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "event_data": self.event_data,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventEnvelope":
        """Deserialize envelope."""
        return cls(
            aggregate_type=data["aggregate_type"],
            aggregate_id=data["aggregate_id"],
            aggregate_version=data["aggregate_version"],
            sequence_number=data["sequence_number"],
            event_type=data["event_type"],
            event_version=data["event_version"],
            event_data=data["event_data"],
            metadata=EventMetadata.from_dict(data["metadata"]),
        )


__all__ = [
    "DomainEvent",
    "EventMetadata",
    "EventEnvelope",
]
