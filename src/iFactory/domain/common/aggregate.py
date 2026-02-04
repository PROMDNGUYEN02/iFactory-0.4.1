# src/iFactory/domain/common/aggregate.py
"""
Enhanced Aggregate Root with versioning and optimistic concurrency.

Features:
- Version tracking for optimistic concurrency
- Event sequencing within aggregate
- Snapshot support for event sourcing
- Invariant validation hooks
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from .entity import Entity
from .event import DomainEvent, EventEnvelope, EventMetadata


T = TypeVar("T", bound="AggregateRoot")


class ConcurrencyError(Exception):
    """Raised when optimistic concurrency check fails."""

    def __init__(
        self,
        aggregate_type: str,
        aggregate_id: str,
        expected_version: int,
        actual_version: int,
    ):
        self.aggregate_type = aggregate_type
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Concurrency conflict on {aggregate_type}[{aggregate_id}]: " f"expected version {expected_version}, but found {actual_version}"
        )


@dataclass(frozen=True)
class AggregateSnapshot:
    """
    Snapshot of aggregate state for event sourcing optimization.
    """

    aggregate_type: str
    aggregate_id: str
    version: int
    state: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "version": self.version,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregateSnapshot":
        return cls(
            aggregate_type=data["aggregate_type"],
            aggregate_id=data["aggregate_id"],
            version=data["version"],
            state=data["state"],
            created_at=(datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]),
        )


class AggregateRoot(ABC):
    """
    Enhanced Aggregate Root with versioning and event sourcing support.

    An Aggregate Root is the entry point to an aggregate - a cluster
    of domain objects that are treated as a single unit for data changes.

    Features:
    - Version tracking for optimistic concurrency
    - Domain event recording with sequencing
    - Snapshot support for event sourcing
    - Invariant validation hooks

    Usage:
        class Order(AggregateRoot):
            def __init__(self, order_id: str):
                super().__init__()
                self._id = order_id
                self._items: List[OrderItem] = []
                self._status = OrderStatus.DRAFT

            @property
            def aggregate_id(self) -> str:
                return self._id

            def add_item(self, item: OrderItem) -> None:
                self._validate_can_modify()
                self._items.append(item)
                self._record_event(ItemAddedEvent(...))

            def _validate_invariants(self) -> None:
                if not self._items and self._status != OrderStatus.DRAFT:
                    raise DomainError("Order must have at least one item")
    """

    __slots__ = (
        "_domain_events",
        "_version",
        "_event_sequence",
        "_created_at",
        "_modified_at",
    )

    def __init__(self) -> None:
        self._domain_events: List[DomainEvent] = []
        self._version: int = 0
        self._event_sequence: int = 0
        self._created_at: datetime = datetime.now()
        self._modified_at: datetime = datetime.now()

    # ========================================================================
    # Abstract Properties (must implement in subclass)
    # ========================================================================

    @property
    @abstractmethod
    def aggregate_id(self) -> str:
        """Unique identifier for this aggregate instance."""
        raise NotImplementedError

    # ========================================================================
    # Version Management
    # ========================================================================

    @property
    def version(self) -> int:
        """Current version for optimistic concurrency."""
        return self._version

    @property
    def created_at(self) -> datetime:
        """When aggregate was created."""
        return self._created_at

    @property
    def modified_at(self) -> datetime:
        """When aggregate was last modified."""
        return self._modified_at

    def _increment_version(self) -> None:
        """Increment version after successful persistence."""
        self._version += 1
        self._modified_at = datetime.now()

    def check_version(self, expected_version: int) -> None:
        """
        Check version for optimistic concurrency.

        Raises:
            ConcurrencyError: If versions don't match
        """
        if self._version != expected_version:
            raise ConcurrencyError(
                aggregate_type=self.__class__.__name__,
                aggregate_id=self.aggregate_id,
                expected_version=expected_version,
                actual_version=self._version,
            )

    def set_version(self, version: int) -> None:
        """Set version (used when loading from persistence)."""
        self._version = version

    def set_timestamps(
        self,
        created_at: Optional[datetime] = None,
        modified_at: Optional[datetime] = None,
    ) -> None:
        """Set timestamps (used when loading from persistence)."""
        if created_at:
            self._created_at = created_at
        if modified_at:
            self._modified_at = modified_at

    # ========================================================================
    # Event Management
    # ========================================================================

    def _record_event(
        self,
        event: DomainEvent,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        """
        Record a domain event with proper sequencing.

        Args:
            event: The domain event to record
            metadata: Optional metadata to attach
        """
        # Add metadata if provided
        if metadata:
            event = event.with_metadata(metadata)

        self._domain_events.append(event)
        self._event_sequence += 1
        self._modified_at = datetime.now()

    def collect_events(self) -> List[DomainEvent]:
        """
        Returns and clears all recorded domain events.

        Call this AFTER successful persistence.
        """
        events = self._domain_events[:]
        self._domain_events.clear()
        return events

    def peek_events(self) -> List[DomainEvent]:
        """Returns events WITHOUT clearing them."""
        return self._domain_events[:]

    def clear_events(self) -> None:
        """Clears pending events without returning them."""
        self._domain_events.clear()

    @property
    def has_pending_events(self) -> bool:
        """Check if there are pending events."""
        return len(self._domain_events) > 0

    @property
    def pending_event_count(self) -> int:
        """Number of pending events."""
        return len(self._domain_events)

    def get_event_envelopes(self) -> List[EventEnvelope]:
        """
        Get events wrapped in envelopes for storage/transport.
        """
        envelopes = []
        base_sequence = self._event_sequence - len(self._domain_events)

        for i, event in enumerate(self._domain_events):
            envelope = EventEnvelope(
                aggregate_type=self.__class__.__name__,
                aggregate_id=self.aggregate_id,
                aggregate_version=self._version,
                sequence_number=base_sequence + i + 1,
                event_type=event.event_type,
                event_version=event.version,
                event_data=event.to_dict(),
                metadata=event.metadata,
            )
            envelopes.append(envelope)

        return envelopes

    # ========================================================================
    # Invariant Validation
    # ========================================================================

    def _validate_invariants(self) -> None:
        """
        Validate aggregate invariants.

        Override in subclasses to enforce business rules.
        Called automatically before event recording.

        Raises:
            DomainException: If any invariant is violated
        """
        pass

    def validate(self) -> None:
        """Public validation method."""
        self._validate_invariants()

    # ========================================================================
    # Snapshot Support
    # ========================================================================

    def to_snapshot(self) -> AggregateSnapshot:
        """
        Create a snapshot of current state.

        Override _get_snapshot_state() to customize serialization.
        """
        return AggregateSnapshot(
            aggregate_type=self.__class__.__name__,
            aggregate_id=self.aggregate_id,
            version=self._version,
            state=self._get_snapshot_state(),
        )

    def _get_snapshot_state(self) -> Dict[str, Any]:
        """
        Get state for snapshot. Override in subclasses.
        """
        state: Dict[str, Any] = {}
        for name in dir(self):
            if not name.startswith("_") and not callable(getattr(self, name)):
                try:
                    value = getattr(self, name)
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        state[name] = value
                except Exception:
                    pass
        return state

    @classmethod
    def from_snapshot(cls: Type[T], snapshot: AggregateSnapshot) -> T:
        """
        Restore aggregate from snapshot.

        Override in subclasses for proper restoration.
        """
        raise NotImplementedError(f"{cls.__name__} must implement from_snapshot for restoration")

    # ========================================================================
    # Equality (based on identity)
    # ========================================================================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AggregateRoot):
            return NotImplemented
        return self.__class__ == other.__class__ and self.aggregate_id == other.aggregate_id

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.aggregate_id))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(" f"id={self.aggregate_id}, " f"version={self._version}, " f"events={len(self._domain_events)})"


__all__ = [
    "AggregateRoot",
    "AggregateSnapshot",
    "ConcurrencyError",
]
