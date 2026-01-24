"""
Domain Events Package.
"""

from __future__ import annotations

from .device_status_changed import StatusChangedEvent, DomainEvent

__all__ = ["DomainEvent", "StatusChangedEvent"]
