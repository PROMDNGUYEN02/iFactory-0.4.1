# src/iFactory/domain/__init__.py
"""
iFactory Domain Layer.

This layer contains the core business logic, completely independent of
infrastructure concerns. It defines:

- Entities: Objects with identity (Device)
- Value Objects: Immutable value types (EquipmentCode, TimeRange, etc.)
- Domain Events: Facts about what happened (StatusChangedEvent)
- Policies: Business rules (StatusTransitionPolicy)
- Repository Interfaces: Ports for persistence
- Domain Exceptions: Business rule violations

Design Principles:
- No dependencies on infrastructure (pure Python)
- Rich domain model (logic lives in entities/value objects)
- Explicit exceptions for rule violations
- Event-driven for state changes
"""

# Common building blocks
from .common import (
    Entity,
    AggregateRoot,
    ValueObject,
    DomainEvent,
    EventMetadata,
)

# Entities
from .entities import Device

# Value Objects
from .value_objects import (
    EquipmentCode,
    TimeRange,
    StatusPeriod,
)

# Enums
from .enums import MachineStatus

# Events
from .events import StatusChangedEvent

# Policies
from .policies import StatusTransitionPolicy

# Exceptions
from .exceptions import (
    DomainError,
    InvalidEquipmentCodeError,
    InvalidStatusTransitionError,
    DeviceNotFoundError,
    InvalidTimeRangeError,
)

# Repository interfaces (ports)
from .repositories import DeviceRepository

__all__ = [
    # Common
    "Entity",
    "AggregateRoot",
    "ValueObject",
    "DomainEvent",
    "EventMetadata",
    # Entities
    "Device",
    # Value Objects
    "EquipmentCode",
    "TimeRange",
    "StatusPeriod",
    # Enums
    "MachineStatus",
    # Events
    "StatusChangedEvent",
    # Policies
    "StatusTransitionPolicy",
    # Exceptions
    "DomainError",
    "InvalidEquipmentCodeError",
    "InvalidStatusTransitionError",
    "DeviceNotFoundError",
    "InvalidTimeRangeError",
    # Repositories
    "DeviceRepository",
]
