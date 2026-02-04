# src/iFactory/domain/events/__init__.py
"""
Domain Events.

Events represent facts about things that happened in the domain.
They are named in past tense and are immutable.
"""

from .device_events import StatusChangedEvent

__all__ = [
    "StatusChangedEvent",
]
