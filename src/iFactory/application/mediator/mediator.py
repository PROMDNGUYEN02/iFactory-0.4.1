# src/iFactory/application/mediator/mediator.py
"""
Mediator implementation - Central dispatcher for requests and notifications.

Features:
- Type-safe request/response handling
- Pipeline behaviors for cross-cutting concerns
- Notification (event) publishing
- Dependency injection support
- Metrics and monitoring
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    Awaitable,
)
from weakref import WeakValueDictionary

from .request import IRequest, IRequestHandler, HandlerNotFoundError
from .notification import INotification, INotificationHandler
from .behaviors import IPipelineBehavior

logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse")
TRequest = TypeVar("TRequest", bound=IRequest)
TNotification = TypeVar("TNotification", bound=INotification)

# Type for handler factories
HandlerFactory = Callable[[], IRequestHandler[Any]]
NotificationHandlerFactory = Callable[[], INotificationHandler[Any]]


class IMediator(ABC):
    """
    Mediator interface for decoupled request handling.

    Implements the Mediator pattern for CQRS:
    - Commands and Queries are sent via send()
    - Events/Notifications are published via publish()
    """

    @abstractmethod
    async def send(self, request: IRequest[TResponse]) -> TResponse:
        """Send a request and get response."""
        pass

    @abstractmethod
    async def publish(self, notification: INotification) -> None:
        """Publish a notification to all handlers."""
        pass


class Mediator(IMediator):
    """
    Central mediator for request/response and notification handling.

    Features:
    - Request -> Handler mapping with factories
    - Pipeline behaviors for cross-cutting concerns
    - Notification publishing with parallel execution
    - Handler caching for performance
    - Comprehensive error handling

    Usage:
        mediator = Mediator()

        # Register handlers
        mediator.register_handler(GetDeviceQuery, GetDeviceHandler)
        mediator.register_handler_factory(
            CreateOrderCommand,
            lambda: CreateOrderHandler(uow_factory)
        )

        # Register behaviors (order matters - first registered = outermost)
        mediator.use(LoggingBehavior())
        mediator.use(ValidationBehavior())
        mediator.use(CachingBehavior())

        # Send request
        result = await mediator.send(GetDeviceQuery(device_id="DEV001"))

        # Publish notification
        await mediator.publish(OrderCreatedNotification(order_id="ORD001"))
    """

    def __init__(
        self,
        cache_handlers: bool = True,
        stop_on_notification_error: bool = False,
    ) -> None:
        """
        Initialize mediator.

        Args:
            cache_handlers: Whether to cache handler instances
            stop_on_notification_error: Whether to stop on first notification handler error
        """
        # Handler registrations
        self._handler_types: Dict[Type, Type[IRequestHandler]] = {}
        self._handler_factories: Dict[Type, HandlerFactory] = {}
        self._handler_instances: Dict[Type, IRequestHandler] = {}

        # Handler cache (weak references to allow GC)
        self._handler_cache: WeakValueDictionary = WeakValueDictionary() if cache_handlers else {}
        self._cache_handlers = cache_handlers

        # Pipeline behaviors
        self._behaviors: List[IPipelineBehavior] = []

        # Notification handlers
        self._notification_handlers: Dict[Type, List[INotificationHandler]] = {}
        self._notification_factories: Dict[Type, List[NotificationHandlerFactory]] = {}

        self._stop_on_notification_error = stop_on_notification_error

        # Metrics
        self._request_count = 0
        self._notification_count = 0

    # ========================================================================
    # Handler Registration
    # ========================================================================

    def register_handler(
        self,
        request_type: Type[IRequest[TResponse]],
        handler_type: Type[IRequestHandler[TResponse]],
    ) -> "Mediator":
        """
        Register a handler type for a request type.

        Handler will be instantiated on first use.
        """
        self._handler_types[request_type] = handler_type
        logger.debug(f"Registered handler {handler_type.__name__} for {request_type.__name__}")
        return self

    def register_handler_factory(
        self,
        request_type: Type[IRequest[TResponse]],
        factory: HandlerFactory,
    ) -> "Mediator":
        """
        Register a factory function for creating handler instances.

        Use this when handler needs dependencies injected.
        """
        self._handler_factories[request_type] = factory
        logger.debug(f"Registered handler factory for {request_type.__name__}")
        return self

    def register_handler_instance(
        self,
        request_type: Type[IRequest[TResponse]],
        handler: IRequestHandler[TResponse],
    ) -> "Mediator":
        """
        Register a pre-created handler instance.

        Use this for singleton handlers.
        """
        self._handler_instances[request_type] = handler
        logger.debug(f"Registered handler instance for {request_type.__name__}")
        return self

    def register_notification_handler(
        self,
        notification_type: Type[TNotification],
        handler: Union[INotificationHandler[TNotification], NotificationHandlerFactory],
    ) -> "Mediator":
        """
        Register a notification handler or factory.

        Multiple handlers can be registered for the same notification type.
        """
        if callable(handler) and not isinstance(handler, INotificationHandler):
            # It's a factory
            if notification_type not in self._notification_factories:
                self._notification_factories[notification_type] = []
            self._notification_factories[notification_type].append(handler)
        else:
            # It's an instance
            if notification_type not in self._notification_handlers:
                self._notification_handlers[notification_type] = []
            self._notification_handlers[notification_type].append(handler)

        return self

    # ========================================================================
    # Behavior Registration
    # ========================================================================

    def use(self, behavior: IPipelineBehavior) -> "Mediator":
        """
        Add a pipeline behavior.

        Behaviors are executed in registration order (first = outermost).
        """
        self._behaviors.append(behavior)
        logger.debug(f"Added behavior: {type(behavior).__name__}")
        return self

    def clear_behaviors(self) -> "Mediator":
        """Remove all pipeline behaviors."""
        self._behaviors.clear()
        return self

    # ========================================================================
    # Request Handling
    # ========================================================================

    async def send(self, request: IRequest[TResponse]) -> TResponse:
        """
        Send a request through the pipeline to its handler.

        Args:
            request: The request to handle

        Returns:
            Response from handler

        Raises:
            HandlerNotFoundError: If no handler registered for request type
        """
        self._request_count += 1
        request_type = type(request)
        request_name = request_type.__name__

        # Get or create handler
        handler = self._get_handler(request_type)
        if handler is None:
            raise HandlerNotFoundError(request_type)

        # Build pipeline with behaviors
        async def final_handler(req: IRequest[TResponse]) -> TResponse:
            return await handler.handle(req)

        pipeline = self._build_pipeline(final_handler)

        # Execute pipeline
        try:
            return await pipeline(request)
        except Exception as e:
            logger.error(f"Request {request_name} failed: {e}")
            raise

    def _get_handler(self, request_type: Type) -> Optional[IRequestHandler]:
        """Get handler instance for request type with caching."""
        # Check instance registry first
        if request_type in self._handler_instances:
            return self._handler_instances[request_type]

        # Check cache
        if self._cache_handlers and request_type in self._handler_cache:
            cached = self._handler_cache.get(request_type)
            if cached is not None:
                return cached

        # Try factory
        if request_type in self._handler_factories:
            handler = self._handler_factories[request_type]()
            if self._cache_handlers:
                self._handler_cache[request_type] = handler
            return handler

        # Try type (create new instance)
        if request_type in self._handler_types:
            handler_type = self._handler_types[request_type]
            handler = handler_type()
            if self._cache_handlers:
                self._handler_cache[request_type] = handler
            return handler

        return None

    def _build_pipeline(
        self,
        final_handler: Callable[[IRequest[TResponse]], Awaitable[TResponse]],
    ) -> Callable[[IRequest[TResponse]], Awaitable[TResponse]]:
        """Build the behavior pipeline wrapping the final handler."""
        if not self._behaviors:
            return final_handler

        # Build chain from inside out (last behavior wraps final handler)
        current = final_handler

        for behavior in reversed(self._behaviors):
            # Capture behavior and next handler in closure
            next_handler = current

            async def create_step(
                b: IPipelineBehavior,
                next_h: Callable,
                req: IRequest[TResponse],
            ) -> TResponse:
                return await b.handle(req, next_h)

            # Use lambda with default args to capture current values
            current = lambda req, b=behavior, h=next_handler: create_step(b, h, req)

        return current

    # ========================================================================
    # Notification Publishing
    # ========================================================================

    async def publish(self, notification: INotification) -> None:
        """
        Publish a notification to all registered handlers.

        Handlers are called in parallel. Errors in one handler
        don't affect others (unless stop_on_notification_error is True).
        """
        self._notification_count += 1
        notification_type = type(notification)

        # Get all handlers (instances + factories)
        handlers: List[INotificationHandler] = list(self._notification_handlers.get(notification_type, []))

        # Add handlers from factories
        for factory in self._notification_factories.get(notification_type, []):
            try:
                handlers.append(factory())
            except Exception as e:
                logger.error(f"Failed to create notification handler: {e}")

        if not handlers:
            logger.debug(f"No handlers for notification: {notification_type.__name__}")
            return

        # Execute handlers in parallel
        tasks = [self._safe_handle_notification(handler, notification) for handler in handlers]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = type(handlers[i]).__name__
                logger.error(f"Notification handler {handler_name} failed: {result}")
                if self._stop_on_notification_error:
                    raise result

    async def _safe_handle_notification(
        self,
        handler: INotificationHandler,
        notification: INotification,
    ) -> None:
        """Handle notification with error isolation."""
        try:
            result = handler.handle(notification)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            # Re-raise to be caught by gather
            raise

    # ========================================================================
    # Utilities
    # ========================================================================

    def has_handler(self, request_type: Type) -> bool:
        """Check if a handler is registered for request type."""
        return request_type in self._handler_instances or request_type in self._handler_factories or request_type in self._handler_types

    def clear(self) -> None:
        """Remove all handlers, behaviors, and reset state."""
        self._handler_types.clear()
        self._handler_factories.clear()
        self._handler_instances.clear()
        self._handler_cache.clear()
        self._behaviors.clear()
        self._notification_handlers.clear()
        self._notification_factories.clear()
        self._request_count = 0
        self._notification_count = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get mediator statistics."""
        return {
            "request_count": self._request_count,
            "notification_count": self._notification_count,
            "registered_handlers": len(self._handler_types) + len(self._handler_factories) + len(self._handler_instances),
            "registered_behaviors": len(self._behaviors),
            "cached_handlers": len(self._handler_cache) if self._cache_handlers else 0,
        }


# ============================================================================
# Singleton Access
# ============================================================================

_default_mediator: Optional[Mediator] = None


def get_mediator() -> Mediator:
    """Get the default mediator instance."""
    global _default_mediator
    if _default_mediator is None:
        _default_mediator = Mediator()
    return _default_mediator


def set_mediator(mediator: Mediator) -> None:
    """Set the default mediator instance."""
    global _default_mediator
    _default_mediator = mediator


def reset_mediator() -> None:
    """Reset the default mediator (for testing)."""
    global _default_mediator
    if _default_mediator:
        _default_mediator.clear()
    _default_mediator = None


__all__ = [
    "IMediator",
    "Mediator",
    "get_mediator",
    "set_mediator",
    "reset_mediator",
]
