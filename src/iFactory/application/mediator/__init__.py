# src/application/mediator/__init__.py
"""
MediatR-like Mediator Pattern Implementation.

Features:
- Request/Response handling
- Pipeline behaviors for cross-cutting concerns
- Notification (event) publishing
- Async-first design
"""

from .mediator import Mediator, IMediator
from .request import Request, IRequest, IRequestHandler
from .notification import Notification, INotification, INotificationHandler
from .behaviors import (
    IPipelineBehavior,
    ValidationBehavior,
    LoggingBehavior,
    CachingBehavior,
    TransactionBehavior,
    RetryBehavior,
    MetricsBehavior,
)
from .pipeline import Pipeline

__all__ = [
    # Core
    "Mediator",
    "IMediator",
    "Pipeline",
    # Request
    "Request",
    "IRequest",
    "IRequestHandler",
    # Notification
    "Notification",
    "INotification",
    "INotificationHandler",
    # Behaviors
    "IPipelineBehavior",
    "ValidationBehavior",
    "LoggingBehavior",
    "CachingBehavior",
    "TransactionBehavior",
    "RetryBehavior",
    "MetricsBehavior",
]
