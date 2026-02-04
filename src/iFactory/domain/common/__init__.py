# src/iFactory/domain/common/__init__.py
"""
Domain Common Building Blocks.
"""

from .aggregate import AggregateRoot, AggregateSnapshot, ConcurrencyError
from .entity import Entity, TId
from .event import DomainEvent, EventEnvelope, EventMetadata
from .event_dispatcher import (
    CorrelationMiddleware,
    DeadLetterQueue,
    DispatcherMetrics,
    EnhancedEventDispatcher,
    EventMiddleware,
    FailedEvent,
    IEventDispatcher,
    InMemoryDeadLetterQueue,
    InMemoryEventDispatcher,
    LoggingMiddleware,
    RetryMiddleware,
    get_event_dispatcher,
    reset_event_dispatcher,
)
from .value_object import SingleValueObject, ValueObject


__all__ = [
    "AggregateRoot",
    "AggregateSnapshot",
    "ConcurrencyError",
    "CorrelationMiddleware",
    "DeadLetterQueue",
    "DispatcherMetrics",
    "DomainEvent",
    "EnhancedEventDispatcher",
    "Entity",
    "EventEnvelope",
    "EventMetadata",
    "EventMiddleware",
    "FailedEvent",
    "IEventDispatcher",
    "InMemoryDeadLetterQueue",
    "InMemoryEventDispatcher",
    "LoggingMiddleware",
    "RetryMiddleware",
    "SingleValueObject",
    "TId",
    "ValueObject",
    "get_event_dispatcher",
    "reset_event_dispatcher",
]
