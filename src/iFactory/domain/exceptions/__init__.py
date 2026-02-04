# src/iFactory/domain/exceptions/__init__.py
"""
Domain Exceptions.

All domain-layer exceptions are exposed here for convenient importing.
"""

from .base import (
    DomainError,
    DomainValidationError,
    DomainInvariantError,
    EntityNotFoundError,
    BusinessRuleViolationError,
)

from .domain_exceptions import (
    InvalidEquipmentCodeError,
    DeviceNotFoundError,
    InvalidStatusTransitionError,
    InvalidTransitionError,
    StaleDataError,
    InvalidTimeRangeError,
    StatusMergeError,
    InvalidMaterialError,
)

__all__ = [
    # Base
    "DomainError",
    "DomainValidationError",
    "DomainInvariantError",
    "EntityNotFoundError",
    "BusinessRuleViolationError",
    # Domain-specific
    "InvalidEquipmentCodeError",
    "DeviceNotFoundError",
    "InvalidStatusTransitionError",
    "InvalidTransitionError",
    "StaleDataError",
    "InvalidTimeRangeError",
    "StatusMergeError",
    "InvalidMaterialError",
]
