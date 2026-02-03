# File: domain/common/event_dispatcher.py
"""
Domain Event Dispatcher.

Simple in-process event dispatcher for domain events.
For production scale, this can be extended to use message queues.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Type, Union, Awaitable

from .event import DomainEvent

logger = logging.getLogger(__name__)

# Type aliases
SyncHandler = Callable[[DomainEvent], None]
AsyncHandler = Callable[[DomainEvent], Awaitable[None]]
EventHandler = Union[SyncHandler, AsyncHandler]


class IEventDispatcher(ABC):
    """Port interface for event dispatching."""

    @abstractmethod
    def register(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
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


class InMemoryEventDispatcher(IEventDispatcher):
    """
    In-memory event dispatcher for domain events.

    Features:
    - Supports both sync and async handlers
    - Type-safe handler registration
    - Error isolation (one handler failure doesn't stop others)
    - Logging for debugging

    Usage:
        dispatcher = InMemoryEventDispatcher()

        # Register handler
        async def on_status_changed(event: StatusChangedEvent):
            await notify_operators(event)

        dispatcher.register(StatusChangedEvent, on_status_changed)

        # Dispatch events from aggregate
        events = device.collect_events()
        await dispatcher.dispatch_all(events)
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type[DomainEvent], List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []

    def register(self, event_type: Type[DomainEvent], handler: EventHandler) -> None:
        """
        Register a handler for a specific event type.

        Args:
            event_type: The DomainEvent subclass to handle.
            handler: Sync or async callable that accepts the event.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)
        logger.debug("Registered handler %s for event %s", handler.__name__ if hasattr(handler, "__name__") else str(handler), event_type.__name__)

    def register_global(self, handler: EventHandler) -> None:
        """
        Register a handler that receives ALL events.

        Useful for logging, metrics, audit trails.
        """
        self._global_handlers.append(handler)
        logger.debug("Registered global handler %s", handler)

    def unregister(self, event_type: Type[DomainEvent], handler: EventHandler) -> bool:
        """Remove a handler. Returns True if found and removed."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    async def dispatch(self, event: DomainEvent) -> None:
        """
        Dispatch a single event to all registered handlers.

        Handlers are called in registration order.
        Errors in one handler don't prevent other handlers from running.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, []) + self._global_handlers

        if not handlers:
            logger.debug("No handlers for event: %s", event_type.__name__)
            return

        logger.debug("Dispatching %s to %d handlers", event_type.__name__, len(handlers))

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                # Log but don't re-raise - other handlers should still run
                logger.error(
                    "Handler %s failed for event %s: %s",
                    handler.__name__ if hasattr(handler, "__name__") else str(handler),
                    event_type.__name__,
                    e,
                    exc_info=True,
                )

    async def dispatch_all(self, events: List[DomainEvent]) -> None:
        """
        Dispatch multiple events in order.

        Events are dispatched sequentially to maintain ordering.
        """
        for event in events:
            await self.dispatch(event)

    def clear(self) -> None:
        """Remove all handlers (useful for testing)."""
        self._handlers.clear()
        self._global_handlers.clear()


# Singleton instance for simple usage
_default_dispatcher: InMemoryEventDispatcher | None = None


def get_event_dispatcher() -> InMemoryEventDispatcher:
    """Get the default event dispatcher instance."""
    global _default_dispatcher
    if _default_dispatcher is None:
        _default_dispatcher = InMemoryEventDispatcher()
    return _default_dispatcher


def reset_event_dispatcher() -> None:
    """Reset the default dispatcher (for testing)."""
    global _default_dispatcher
    if _default_dispatcher:
        _default_dispatcher.clear()
    _default_dispatcher = None


__all__ = [
    "IEventDispatcher",
    "InMemoryEventDispatcher",
    "get_event_dispatcher",
    "reset_event_dispatcher",
]
