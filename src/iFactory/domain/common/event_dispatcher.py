# src/domain/common/event_dispatcher.py - ENHANCED
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
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Protocol, Set, Type, TypeVar, Union

from .event import DomainEvent, EventMetadata

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=DomainEvent)


# ============================================================================
# Handler Types
# ============================================================================


class EventHandler(Protocol[E]):
    """Protocol for event handlers."""

    async def handle(self, event: E) -> None:
        """Handle the event."""
        ...


SyncHandler = Callable[[DomainEvent], None]
AsyncHandler = Callable[[DomainEvent], Awaitable[None]]
AnyHandler = Union[SyncHandler, AsyncHandler, EventHandler]


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
        next_handler: Callable[[DomainEvent], Awaitable[None]],
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
        next_handler: Callable[[DomainEvent], Awaitable[None]],
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
        next_handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        if not event.correlation_id and self._default_id:
            # Create new event with correlation ID
            metadata = event.metadata.with_correlation(self._default_id)
            event = event.with_metadata(metadata)

        await next_handler(event)


class RetryMiddleware(EventMiddleware):
    """Retry failed handlers with backoff."""

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
        next_handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        last_error = None

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

        raise last_error  # type: ignore


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
    """In-memory dead letter queue for development."""

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
            "success_rate": self.success_rate,
            "avg_processing_ms": self.avg_processing_ms,
        }


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
        """Add middleware to the pipeline."""
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
        logger.debug("[EventDispatcher] Registered global handler")

    def unregister(
        self,
        event_type: Type[DomainEvent],
        handler: AnyHandler,
    ) -> bool:
        """Remove a handler. Returns True if found."""
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
            # Build middleware chain
            async def final_handler(evt: DomainEvent) -> None:
                await self._invoke_handlers(evt)

            chain = self._build_middleware_chain(final_handler)
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

    def _build_middleware_chain(
        self,
        final: Callable[[DomainEvent], Awaitable[None]],
    ) -> Callable[[DomainEvent], Awaitable[None]]:
        """Build middleware chain ending with final handler."""
        handler = final

        for middleware in reversed(self._middleware):
            current_handler = handler

            async def make_handler(
                mw: EventMiddleware,
                next_h: Callable[[DomainEvent], Awaitable[None]],
            ) -> Callable[[DomainEvent], Awaitable[None]]:
                async def wrapper(evt: DomainEvent) -> None:
                    await mw.process(evt, next_h)

                return wrapper

            # Create closure properly
            handler = asyncio.coroutine(lambda evt, mw=middleware, h=current_handler: mw.process(evt, h))

        return handler

    async def _invoke_handlers(self, event: DomainEvent) -> None:
        """Invoke all handlers for an event."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, []) + self._global_handlers

        if not handlers:
            logger.debug(
                "[EventDispatcher] No handlers for %s",
                event_type.__name__,
            )
            return

        for handler in handlers:
            self._metrics.handlers_invoked += 1
            handler_name = getattr(handler, "__name__", str(handler))

            try:
                # Handle different handler types
                if hasattr(handler, "handle"):
                    # EventHandler protocol
                    result = handler.handle(event)
                else:
                    # Callable
                    result = handler(event)

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
        self._metrics = DispatcherMetrics()

    async def get_dead_letter_count(self) -> int:
        """Get number of failed events in DLQ."""
        return await self._dlq.size()

    async def retry_dead_letters(self, count: int = 10) -> int:
        """Retry failed events from DLQ. Returns number retried."""
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
    """
    Backward-compatible alias for EnhancedEventDispatcher.
    """

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
