# src/application/mediator/mediator.py
"""
Mediator implementation - Central dispatcher for requests and notifications.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, get_type_hints, get_origin, get_args

from .request import IRequest, IRequestHandler
from .notification import INotification, INotificationHandler
from .behaviors import IPipelineBehavior

logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse")
TNotification = TypeVar("TNotification", bound=INotification)


class IMediator(ABC):
    """
    Mediator interface for decoupled request handling.
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
    - Request -> Handler mapping
    - Pipeline behaviors for cross-cutting concerns
    - Notification publishing
    - Handler factory support

    Usage:
        mediator = Mediator()

        # Register handlers
        mediator.register_handler(GetDeviceQuery, GetDeviceHandler)
        mediator.register_handler(CreateOrderCommand, CreateOrderHandler)

        # Register behaviors (order matters!)
        mediator.use(LoggingBehavior())
        mediator.use(ValidationBehavior())
        mediator.use(CachingBehavior())

        # Send request
        result = await mediator.send(GetDeviceQuery(device_id="DEV001"))

        # Publish notification
        await mediator.publish(OrderCreatedNotification(order_id="ORD001"))
    """

    def __init__(self):
        self._handlers: Dict[Type, Type[IRequestHandler]] = {}
        self._handler_factories: Dict[Type, Callable[[], IRequestHandler]] = {}
        self._handler_instances: Dict[Type, IRequestHandler] = {}
        self._behaviors: List[IPipelineBehavior] = []
        self._notification_handlers: Dict[Type, List[INotificationHandler]] = {}

    # ========================================================================
    # Handler Registration
    # ========================================================================

    def register_handler(
        self,
        request_type: Type[IRequest],
        handler_type: Type[IRequestHandler],
    ) -> "Mediator":
        """Register a handler type for a request type."""
        self._handlers[request_type] = handler_type
        return self

    def register_handler_factory(
        self,
        request_type: Type[IRequest],
        factory: Callable[[], IRequestHandler],
    ) -> "Mediator":
        """Register a factory function for creating handler instances."""
        self._handler_factories[request_type] = factory
        return self

    def register_handler_instance(
        self,
        request_type: Type[IRequest],
        handler: IRequestHandler,
    ) -> "Mediator":
        """Register a pre-created handler instance."""
        self._handler_instances[request_type] = handler
        return self

    def register_notification_handler(
        self,
        notification_type: Type[INotification],
        handler: INotificationHandler,
    ) -> "Mediator":
        """Register a notification handler."""
        if notification_type not in self._notification_handlers:
            self._notification_handlers[notification_type] = []
        self._notification_handlers[notification_type].append(handler)
        return self

    # ========================================================================
    # Behavior Registration
    # ========================================================================

    def use(self, behavior: IPipelineBehavior) -> "Mediator":
        """Add a pipeline behavior."""
        self._behaviors.append(behavior)
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
            KeyError: If no handler registered for request type
        """
        request_type = type(request)

        # Get or create handler
        handler = self._get_handler(request_type)
        if not handler:
            raise KeyError(f"No handler registered for {request_type.__name__}")

        # Build pipeline
        async def final_handler(req: IRequest[TResponse]) -> TResponse:
            return await handler.handle(req)

        pipeline = self._build_pipeline(final_handler)

        # Execute
        return await pipeline(request)

    def _get_handler(self, request_type: Type) -> Optional[IRequestHandler]:
        """Get handler instance for request type."""
        # Check instance cache
        if request_type in self._handler_instances:
            return self._handler_instances[request_type]

        # Check factory
        if request_type in self._handler_factories:
            handler = self._handler_factories[request_type]()
            return handler

        # Check type (create new instance)
        if request_type in self._handlers:
            handler_type = self._handlers[request_type]
            handler = handler_type()
            return handler

        return None

    def _build_pipeline(
        self,
        final: Callable[[IRequest], Any],
    ) -> Callable[[IRequest], Any]:
        """Build the behavior pipeline."""
        handler = final

        # Wrap in behaviors (reverse order for proper nesting)
        for behavior in reversed(self._behaviors):
            current = handler

            async def make_wrapper(
                b: IPipelineBehavior,
                next_h: Callable,
            ) -> Callable:
                async def wrapper(req: IRequest) -> Any:
                    return await b.handle(req, next_h)

                return wrapper

            # Use closure to capture current values
            handler = lambda req, b=behavior, h=current: b.handle(req, h)

        return handler

    # ========================================================================
    # Notification Publishing
    # ========================================================================

    async def publish(self, notification: INotification) -> None:
        """
        Publish a notification to all registered handlers.

        Handlers are called in parallel and errors don't stop other handlers.
        """
        notification_type = type(notification)
        handlers = self._notification_handlers.get(notification_type, [])

        if not handlers:
            logger.debug(f"No handlers for notification: {notification_type.__name__}")
            return

        import asyncio

        tasks = []
        for handler in handlers:
            task = asyncio.create_task(self._safe_handle_notification(handler, notification))
            tasks.append(task)

        await asyncio.gather(*tasks)

    async def _safe_handle_notification(
        self,
        handler: INotificationHandler,
        notification: INotification,
    ) -> None:
        """Handle notification with error isolation."""
        try:
            await handler.handle(notification)
        except Exception as e:
            logger.error(f"Notification handler failed: {type(handler).__name__} - {e}")


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


def reset_mediator() -> None:
    """Reset the default mediator (for testing)."""
    global _default_mediator
    _default_mediator = None


__all__ = [
    "IMediator",
    "Mediator",
    "get_mediator",
    "reset_mediator",
]
