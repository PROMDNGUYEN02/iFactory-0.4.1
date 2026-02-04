# src/iFactory/domain/entities/__init__.py
"""
Domain Entities.

Entities are domain objects with identity that persists over time.
"""

from .device import Device, DeviceState

__all__ = [
    "Device",
    "DeviceState",
]
