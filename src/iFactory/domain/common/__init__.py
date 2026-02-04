# src/iFactory/domain/common/__init__.py
"""
Domain Common Building Blocks.

This module provides the foundational classes for Domain-Driven Design:
- Entity: Objects with identity
- AggregateRoot: Consistency boundaries
- ValueObject: Immutable value types
- DomainEvent: Facts about what happened
- EventDispatcher: Event distribution
"""

from .entity import Entity, TId
from .aggregate import AggregateRoot, AggregateSnapshot, ConcurrencyError
from .value_object import ValueObject, SingleValueObject
from .event import DomainEvent, EventMetadata, EventEnvelope
from .event_dispatcher import (
    IEventDispatcher,
    EnhancedEventDispatcher,
    InMemoryEventDispatcher,
    EventMiddleware,
    LoggingMiddleware,
    CorrelationMiddleware,
    RetryMiddleware,
    get_event_dispatcher,
    reset_event_dispatcher,
)

__all__ = [
    # Entity
    "Entity",
    "TId",
    # Aggregate
    "AggregateRoot",
    "AggregateSnapshot",
    "ConcurrencyError",
    # Value Object
    "ValueObject",
    "SingleValueObject",
    # Event
    "DomainEvent",
    "EventMetadata",
    "EventEnvelope",
    # Dispatcher
    "IEventDispatcher",
    "EnhancedEventDispatcher",
    "InMemoryEventDispatcher",
    "EventMiddleware",
    "LoggingMiddleware",
    "CorrelationMiddleware",
    "RetryMiddleware",
    "get_event_dispatcher",
    "reset_event_dispatcher",
]
