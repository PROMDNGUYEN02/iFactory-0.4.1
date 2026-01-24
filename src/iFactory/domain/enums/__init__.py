"""
Domain Enums Package.

Contains domain enumerations with business semantics.
"""

from __future__ import annotations

from .device_status import DeviceStatus, StatusCode

__all__ = [
    "DeviceStatus",
    "StatusCode",
    # Backward compatibility aliases (deprecated but kept for compatibility)
    "DeviceStatusEnum",
    "StatusCodeEnum",
]

# Add aliases for backward compatibility
DeviceStatusEnum = DeviceStatus
StatusCodeEnum = StatusCode
