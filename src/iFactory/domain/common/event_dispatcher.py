# src/iFactory/domain/common/event_dispatcher.py
"""
Enhanced Domain Event Dispatcher with middleware pipeline.

Features:
- Middleware pipeline for cross-cutting concerns
- Async-first design
- Event filtering and routing
- Dead letter queue for failed events
- Metrics collection
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)

from .event import DomainEvent, EventMetadata

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=DomainEvent)


# ============================================================================
# Handler Types
# ============================================================================


@runtime_checkable
class EventHandler(Protocol[E]):
    """Protocol for event handlers."""

    async def handle(self, event: E) -> None:
        """Handle the event."""
        ...


SyncHandler = Callable[[DomainEvent], None]
AsyncHandler = Callable[[DomainEvent], Awaitable[None]]
AnyHandler = Union[SyncHandler, AsyncHandler, EventHandler[Any]]

# Type for the next handler in middleware chain
NextHandler = Callable[[DomainEvent], Awaitable[None]]


# ============================================================================
# Middleware
# ============================================================================


class EventMiddleware(ABC):
    """
    Base class for event dispatcher middleware.

    Middleware can:
    - Modify events before handling
    - Log/trace event processing
    - Handle errors
    - Filter events
    """

    @abstractmethod
    async def process(
        self,
        event: DomainEvent,
        next_handler: NextHandler,
    ) -> None:
        """
        Process the event and optionally call next handler.

        Args:
            event: The domain event
            next_handler: Next middleware or final handlers
        """
        pass


class LoggingMiddleware(EventMiddleware):
    """Log all events with timing."""

    def __init__(self, log_level: int = logging.DEBUG):
        self._level = log_level

    async def process(
        self,
        event: DomainEvent,
        next_handler: NextHandler,
    ) -> None:
        start = datetime.now()
        logger.log(
            self._level,
            "[EventDispatcher] Processing %s (id=%s)",
            event.event_type,
            event.event_id[:8],
        )

        try:
            await next_handler(event)
            elapsed = (datetime.now() - start).total_seconds() * 1000
            logger.log(
                self._level,
                "[EventDispatcher] Completed %s in %.1fms",
                event.event_type,
                elapsed,
            )
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            logger.error(
                "[EventDispatcher] Failed %s after %.1fms: %s",
                event.event_type,
                elapsed,
                e,
            )
            raise


class CorrelationMiddleware(EventMiddleware):
    """Ensure correlation ID is set."""

    def __init__(self, default_correlation_id: Optional[str] = None):
        self._default_id = default_correlation_id

    async def process(
        self,
        event: DomainEvent,
        next_handler: NextHandler,
    ) -> None:
        if not event.correlation_id and self._default_id:
            metadata = event.metadata.with_correlation(self._default_id)
            event = event.with_metadata(metadata)

        await next_handler(event)


class RetryMiddleware(EventMiddleware):
    """Retry failed handlers with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

    async def process(
        self,
        event: DomainEvent,
        next_handler: NextHandler,
    ) -> None:
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                await next_handler(event)
                return
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = min(
                        self._base_delay * (2**attempt),
                        self._max_delay,
                    )
                    logger.warning(
                        "[EventDispatcher] Retry %d for %s after %.2fs: %s",
                        attempt + 1,
                        event.event_type,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)

        if last_error:
            raise last_error


# ============================================================================
# Dead Letter Queue
# ============================================================================


@dataclass
class FailedEvent:
    """Record of a failed event for dead letter queue."""

    event: DomainEvent
    error: Exception
    handler_name: str
    failed_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0

    def __repr__(self) -> str:
        return f"FailedEvent(event={self.event.event_type}, " f"error={self.error}, retries={self.retry_count})"


class DeadLetterQueue(ABC):
    """Interface for dead letter queue."""

    @abstractmethod
    async def enqueue(self, failed: FailedEvent) -> None:
        """Add failed event to queue."""
        pass

    @abstractmethod
    async def dequeue(self, count: int = 10) -> List[FailedEvent]:
        """Get failed events for retry."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get queue size."""
        pass


class InMemoryDeadLetterQueue(DeadLetterQueue):
    """In-memory dead letter queue for development/testing."""

    def __init__(self, max_size: int = 1000):
        self._queue: List[FailedEvent] = []
        self._max_size = max_size

    async def enqueue(self, failed: FailedEvent) -> None:
        if len(self._queue) >= self._max_size:
            self._queue.pop(0)  # Remove oldest
        self._queue.append(failed)
        logger.warning(
            "[DLQ] Event %s failed: %s (queue size: %d)",
            failed.event.event_type,
            failed.error,
            len(self._queue),
        )

    async def dequeue(self, count: int = 10) -> List[FailedEvent]:
        items = self._queue[:count]
        self._queue = self._queue[count:]
        return items

    async def size(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        """Clear the queue (for testing)."""
        self._queue.clear()


# ============================================================================
# Metrics
# ============================================================================


@dataclass
class DispatcherMetrics:
    """Metrics for event dispatcher."""

    events_dispatched: int = 0
    events_succeeded: int = 0
    events_failed: int = 0
    handlers_invoked: int = 0
    total_processing_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.events_dispatched == 0:
            return 1.0
        return self.events_succeeded / self.events_dispatched

    @property
    def avg_processing_ms(self) -> float:
        if self.events_dispatched == 0:
            return 0.0
        return self.total_processing_ms / self.events_dispatched

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events_dispatched": self.events_dispatched,
            "events_succeeded": self.events_succeeded,
            "events_failed": self.events_failed,
            "handlers_invoked": self.handlers_invoked,
            "success_rate": round(self.success_rate, 4),
            "avg_processing_ms": round(self.avg_processing_ms, 2),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.events_dispatched = 0
        self.events_succeeded = 0
        self.events_failed = 0
        self.handlers_invoked = 0
        self.total_processing_ms = 0.0


# ============================================================================
# Event Dispatcher Interface
# ============================================================================


class IEventDispatcher(ABC):
    """Port interface for event dispatching."""

    @abstractmethod
    def register(
        self,
        event_type: Type[DomainEvent],
        handler: AnyHandler,
    ) -> None:
        """Register a handler for an event type."""
        pass

    @abstractmethod
    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch a single event to all registered handlers."""
        pass

    @abstractmethod
    async def dispatch_all(self, events: List[DomainEvent]) -> None:
        """Dispatch multiple events."""
        pass


# ============================================================================
# Enhanced Dispatcher Implementation
# ============================================================================


class EnhancedEventDispatcher(IEventDispatcher):
    """
    Enhanced event dispatcher with middleware and dead letter queue.

    Features:
    - Middleware pipeline for cross-cutting concerns
    - Dead letter queue for failed events
    - Metrics collection
    - Global and type-specific handlers
    - Async-first design

    Usage:
        dispatcher = EnhancedEventDispatcher()

        # Add middleware
        dispatcher.use(LoggingMiddleware())
        dispatcher.use(RetryMiddleware(max_retries=3))

        # Register handlers
        dispatcher.register(OrderPlaced, notify_customer)
        dispatcher.register(OrderPlaced, update_inventory)
        dispatcher.register_global(audit_logger)

        # Dispatch
        await dispatcher.dispatch(OrderPlacedEvent(...))

        # Check metrics
        print(dispatcher.metrics.to_dict())
    """

    def __init__(
        self,
        dead_letter_queue: Optional[DeadLetterQueue] = None,
        stop_on_error: bool = False,
    ) -> None:
        self._handlers: Dict[Type[DomainEvent], List[AnyHandler]] = defaultdict(list)
        self._global_handlers: List[AnyHandler] = []
        self._middleware: List[EventMiddleware] = []
        self._dlq = dead_letter_queue or InMemoryDeadLetterQueue()
        self._stop_on_error = stop_on_error
        self._metrics = DispatcherMetrics()

    @property
    def metrics(self) -> DispatcherMetrics:
        """Get dispatcher metrics."""
        return self._metrics

    def use(self, middleware: EventMiddleware) -> "EnhancedEventDispatcher":
        """Add middleware to the pipeline. Returns self for chaining."""
        self._middleware.append(middleware)
        return self

    def register(
        self,
        event_type: Type[DomainEvent],
        handler: AnyHandler,
    ) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type].append(handler)
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug(
            "[EventDispatcher] Registered %s for %s",
            handler_name,
            event_type.__name__,
        )

    def register_global(self, handler: AnyHandler) -> None:
        """Register a handler for ALL events."""
        self._global_handlers.append(handler)
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug("[EventDispatcher] Registered global handler: %s", handler_name)

    def unregister(
        self,
        event_type: Type[DomainEvent],
        handler: AnyHandler,
    ) -> bool:
        """Remove a handler. Returns True if found and removed."""
        try:
            self._handlers[event_type].remove(handler)
            return True
        except ValueError:
            return False

    async def dispatch(self, event: DomainEvent) -> None:
        """Dispatch an event through middleware and handlers."""
        self._metrics.events_dispatched += 1
        start = datetime.now()

        try:
            # Build and execute middleware chain
            chain = self._build_middleware_chain()
            await chain(event)
            self._metrics.events_succeeded += 1

        except Exception as e:
            self._metrics.events_failed += 1
            logger.error(
                "[EventDispatcher] Event %s failed: %s",
                event.event_type,
                e,
            )
            if self._stop_on_error:
                raise
        finally:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            self._metrics.total_processing_ms += elapsed

    async def dispatch_all(self, events: List[DomainEvent]) -> None:
        """Dispatch multiple events in order."""
        for event in events:
            await self.dispatch(event)

    def _build_middleware_chain(self) -> NextHandler:
        """Build middleware chain ending with handler invocation."""

        async def final_handler(evt: DomainEvent) -> None:
            await self._invoke_handlers(evt)

        # Build chain from inside out (last middleware wraps final handler)
        chain: NextHandler = final_handler

        for middleware in reversed(self._middleware):
            # Capture middleware and next_chain in closure properly
            chain = self._create_middleware_wrapper(middleware, chain)

        return chain

    def _create_middleware_wrapper(
        self,
        middleware: EventMiddleware,
        next_chain: NextHandler,
    ) -> NextHandler:
        """Create a wrapper for a middleware that captures the next handler."""

        async def wrapper(event: DomainEvent) -> None:
            await middleware.process(event, next_chain)

        return wrapper

    async def _invoke_handlers(self, event: DomainEvent) -> None:
        """Invoke all handlers for an event."""
        event_type = type(event)

        # Get handlers for this specific event type
        type_handlers = list(self._handlers.get(event_type, []))

        # Also check parent classes (for handler inheritance)
        for parent_type in event_type.__mro__:
            if parent_type != event_type and parent_type in self._handlers:
                type_handlers.extend(self._handlers[parent_type])

        # Combine with global handlers
        all_handlers = type_handlers + self._global_handlers

        if not all_handlers:
            logger.debug(
                "[EventDispatcher] No handlers for %s",
                event_type.__name__,
            )
            return

        for handler in all_handlers:
            self._metrics.handlers_invoked += 1
            handler_name = getattr(handler, "__name__", type(handler).__name__)

            try:
                # Handle different handler types
                if isinstance(handler, EventHandler):
                    result = handler.handle(event)
                elif callable(handler):
                    result = handler(event)
                else:
                    logger.warning(
                        "[EventDispatcher] Invalid handler type: %s",
                        type(handler),
                    )
                    continue

                # Await if coroutine
                if asyncio.iscoroutine(result):
                    await result

            except Exception as e:
                logger.error(
                    "[EventDispatcher] Handler %s failed for %s: %s",
                    handler_name,
                    event_type.__name__,
                    e,
                )

                # Add to dead letter queue
                await self._dlq.enqueue(
                    FailedEvent(
                        event=event,
                        error=e,
                        handler_name=handler_name,
                    )
                )

                if self._stop_on_error:
                    raise

    def clear(self) -> None:
        """Remove all handlers and reset metrics."""
        self._handlers.clear()
        self._global_handlers.clear()
        self._metrics.reset()

    def clear_handlers(self) -> None:
        """Remove all handlers but keep metrics."""
        self._handlers.clear()
        self._global_handlers.clear()

    async def get_dead_letter_count(self) -> int:
        """Get number of failed events in DLQ."""
        return await self._dlq.size()

    async def retry_dead_letters(self, count: int = 10) -> int:
        """Retry failed events from DLQ. Returns number successfully retried."""
        failed_events = await self._dlq.dequeue(count)
        retried = 0

        for failed in failed_events:
            try:
                await self.dispatch(failed.event)
                retried += 1
            except Exception:
                # Re-enqueue with incremented retry count
                failed.retry_count += 1
                await self._dlq.enqueue(failed)

        return retried


# ============================================================================
# Legacy Compatible Dispatcher
# ============================================================================


class InMemoryEventDispatcher(EnhancedEventDispatcher):
    """Backward-compatible alias for EnhancedEventDispatcher."""

    pass


# ============================================================================
# Singleton Access
# ============================================================================

_default_dispatcher: Optional[EnhancedEventDispatcher] = None


def get_event_dispatcher() -> EnhancedEventDispatcher:
    """Get the default event dispatcher instance."""
    global _default_dispatcher
    if _default_dispatcher is None:
        _default_dispatcher = EnhancedEventDispatcher()
        _default_dispatcher.use(LoggingMiddleware())
    return _default_dispatcher


def reset_event_dispatcher() -> None:
    """Reset the default dispatcher (for testing)."""
    global _default_dispatcher
    if _default_dispatcher:
        _default_dispatcher.clear()
    _default_dispatcher = None


__all__ = [
    # Interface
    "IEventDispatcher",
    # Implementation
    "EnhancedEventDispatcher",
    "InMemoryEventDispatcher",
    # Handlers
    "EventHandler",
    "SyncHandler",
    "AsyncHandler",
    "AnyHandler",
    # Middleware
    "EventMiddleware",
    "LoggingMiddleware",
    "CorrelationMiddleware",
    "RetryMiddleware",
    # Dead Letter Queue
    "DeadLetterQueue",
    "InMemoryDeadLetterQueue",
    "FailedEvent",
    # Metrics
    "DispatcherMetrics",
    # Singleton
    "get_event_dispatcher",
    "reset_event_dispatcher",
]
