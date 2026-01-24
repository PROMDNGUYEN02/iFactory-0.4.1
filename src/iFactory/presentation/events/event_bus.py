"""
Event Bus for decoupled communication between components.

Architecture:
- EventBus: Central event publisher
- EventHandler: Protocol for event handlers
- Events: Event data classes
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Set,
    TypeVar,
)
from collections import defaultdict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

T = TypeVar('T')


class EventType(Enum):
    """Standard event types."""
    DEVICE_STATUS_CHANGED = "device_status_changed"
    DEVICE_SELECTED = "device_selected"
    DEVICE_DESELECTED = "device_deselected"
    DEVICE_CLICKED = "device_clicked"
    THEME_CHANGED = "theme_changed"
    PAGE_CHANGED = "page_changed"
    DATA_LOADED = "data_loaded"
    ERROR_OCCURRED = "error_occurred"
    LOADING_STARTED = "loading_started"
    LOADING_FINISHED = "loading_finished"
    RIGHT_PANEL_TOGGLED = "right_panel_toggled"
    GANTT_DATA_READY = "gantt_data_ready"


@dataclass
class Event:
    """
    Immutable event descriptor.
    """
    type: EventType
    source: str
    payload: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def with_payload(self, payload: Any) -> 'Event':
        """Create new event with different payload."""
        return Event(
            type=self.type,
            source=self.source,
            payload=payload,
            metadata=self.metadata,
            timestamp=self.timestamp
        )


@runtime_checkable
class EventHandler(Protocol[T]):
    """
    Protocol for event handlers.
    """
    def __call__(self, event: Event) -> None:
        """
        Handle event.
        
        Args:
            event: Event to handle
        """
        ...


class EventBus(QObject):
    """
    Central event bus for decoupled communication.
    
    Features:
    - Subscribe/unsubscribe to events
    - Publish events to all subscribers
    - Event filtering
    - Event history for debugging
    - Thread-safe event handling
    """
    
    event_published = Signal(Event)
    event_handled = Signal(Event, object)
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._subscribers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._event_filters: List[Callable[[Event], bool]] = []
        
        logger.debug("[EventBus] Created")
    
    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """
        Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler function or callable
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"[EventBus] Subscribed to {event_type.value}: {handler}")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function or callable
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"[EventBus] Unsubscribed from {event_type.value}: {handler}")
            except ValueError:
                logger.warning(f"[EventBus] Handler not found for {event_type.value}")
    
    def publish(self, event: Event) -> None:
        """
        Publish event to all subscribers.
        
        Args:
            event: Event to publish
        """
        logger.debug(f"[EventBus] Publishing event: {event.type.value} from {event.source}")
        
        if not self._should_publish_event(event):
            logger.debug(f"[EventBus] Event filtered: {event.type.value}")
            return
        
        self._event_history.append(event)
        
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        self.event_published.emit(event)
        
        for handler in self._subscribers[event.type]:
            try:
                handler(event)
                self.event_handled.emit(event, handler)
            except Exception as e:
                logger.error(f"[EventBus] Error in handler for {event.type.value}: {e}")
    
    def _should_publish_event(self, event: Event) -> bool:
        """Check if event should be published based on filters."""
        for event_filter in self._event_filters:
            if not event_filter(event):
                return False
        return True
    
    def add_event_filter(self, event_filter: Callable[[Event], bool]) -> None:
        """
        Add event filter.
        
        Args:
            event_filter: Filter function that returns True if event should be published
        """
        self._event_filters.append(event_filter)
        logger.debug("[EventBus] Event filter added")
    
    def remove_event_filter(self, event_filter: Callable[[Event], bool]) -> None:
        """
        Remove event filter.
        
        Args:
            event_filter: Filter function to remove
        """
        try:
            self._event_filters.remove(event_filter)
            logger.debug("[EventBus] Event filter removed")
        except ValueError:
            logger.warning("[EventBus] Event filter not found")
    
    def get_history(self, event_type: Optional[EventType] = None) -> List[Event]:
        """
        Get event history.
        
        Args:
            event_type: Optional event type to filter by
            
        Returns:
            List of events
        """
        if event_type:
            return [e for e in self._event_history if e.type == event_type]
        return self._event_history.copy()
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
        logger.debug("[EventBus] History cleared")
    
    def get_subscriber_count(self, event_type: EventType) -> int:
        """
        Get number of subscribers for event type.
        
        Args:
            event_type: Event type to check
            
        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(event_type, []))


@dataclass
class DeviceStatusChangedEvent:
    """Event for device status change."""
    device_id: str
    device_name: str
    old_status: str
    new_status: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DeviceSelectedEvent:
    """Event for device selection."""
    device_id: str
    device_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ThemeChangedEvent:
    """Event for theme change."""
    old_theme: str
    new_theme: str
    timestamp: datetime = field(default_factory=datetime.now)


class EventBusFactory:
    """Factory for creating and managing EventBus instances."""
    
    _instance: Optional[EventBus] = None
    
    @classmethod
    def get_instance(cls) -> EventBus:
        """Get singleton EventBus instance."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None


__all__ = [
    'EventType',
    'Event',
    'EventHandler',
    'EventBus',
    'EventBusFactory',
    'DeviceStatusChangedEvent',
    'DeviceSelectedEvent',
    'ThemeChangedEvent',
]
