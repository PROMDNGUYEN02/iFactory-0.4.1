# src/iFactory/domain/exceptions/__init__.py
"""
Domain Exceptions.
"""

from .base import DomainError
from .domain_exceptions import (
    InvalidEquipmentCodeError,
    InvalidStatusTransitionError,
    InvalidTransitionError,  # Alias
    DeviceNotFoundError,
    StaleDataError,
    InvalidTimeRangeError,
    StatusMergeError,
)

__all__ = [
    "DomainError",
    "InvalidEquipmentCodeError",
    "InvalidStatusTransitionError",
    "InvalidTransitionError",
    "DeviceNotFoundError",
    "StaleDataError",
    "InvalidTimeRangeError",
    "StatusMergeError",
]
