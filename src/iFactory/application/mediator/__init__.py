# src/iFactory/application/mediator/__init__.py
"""MediatR-like Mediator Pattern Implementation."""

from iFactory.application.mediator.mediator import (
    Mediator,
    IMediator,
    get_mediator,
    reset_mediator,
)
from iFactory.application.mediator.request import (
    Request,
    IRequest,
    IRequestHandler,
    Command,
    Query,
    RequestMetadata,
    HandlerNotFoundError,
)
from iFactory.application.mediator.notification import (
    Notification,
    INotification,
    INotificationHandler,
    NotificationMetadata,
    DomainEventNotification,
)
from iFactory.application.mediator.behaviors import (
    IPipelineBehavior,
    IValidator,
    ValidationBehavior,
    LoggingBehavior,
    ICacheProvider,
    InMemoryCache,
    CachingBehavior,
    TransactionBehavior,
    RetryBehavior,
    MetricsBehavior,
    RequestMetrics,
)
from iFactory.application.mediator.pipeline import (
    Pipeline,
    PipelineBuilder,
)

__all__ = [
    # Core
    "Mediator",
    "IMediator",
    "get_mediator",
    "reset_mediator",
    "Pipeline",
    "PipelineBuilder",
    # Request
    "Request",
    "IRequest",
    "IRequestHandler",
    "Command",
    "Query",
    "RequestMetadata",
    "HandlerNotFoundError",
    # Notification
    "Notification",
    "INotification",
    "INotificationHandler",
    "NotificationMetadata",
    "DomainEventNotification",
    # Behaviors
    "IPipelineBehavior",
    "IValidator",
    "ValidationBehavior",
    "LoggingBehavior",
    "ICacheProvider",
    "InMemoryCache",
    "CachingBehavior",
    "TransactionBehavior",
    "RetryBehavior",
    "MetricsBehavior",
    "RequestMetrics",
]
