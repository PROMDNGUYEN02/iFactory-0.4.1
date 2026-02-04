# src/iFactory/application/mediator/notification.py
"""Notification (Event) publishing pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

TNotification = TypeVar("TNotification", bound="INotification")


# ============================================================================
# Interfaces
# ============================================================================


class INotification(ABC):
    """Base interface for notifications (events)."""

    pass


class INotificationHandler(ABC, Generic[TNotification]):
    """Handler interface for processing notifications."""

    @abstractmethod
    async def handle(self, notification: TNotification) -> None:
        """Handle the notification."""
        pass


# ============================================================================
# Metadata
# ============================================================================


@dataclass(frozen=True)
class NotificationMetadata:
    """Metadata for notifications."""

    notification_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: str = ""


# ============================================================================
# Base Classes
# ============================================================================


@dataclass(frozen=True)
class Notification(INotification):
    """Base class for notifications with metadata."""

    metadata: NotificationMetadata = field(default_factory=NotificationMetadata)


@dataclass(frozen=True)
class DomainEventNotification(Notification):
    """Notification wrapper for domain events."""

    event_type: str = ""
    event_data: dict[str, Any] = field(default_factory=dict)
    aggregate_id: str = ""
    aggregate_type: str = ""


__all__ = [
    "INotification",
    "INotificationHandler",
    "Notification",
    "NotificationMetadata",
    "DomainEventNotification",
]
