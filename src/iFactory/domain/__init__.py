# src/iFactory/domain/__init__.py
"""
Domain Layer - Core Business Logic.
"""

# Common Building Blocks
from .common.entity import Entity, TId
from .common.value_object import ValueObject, SingleValueObject
from .common.aggregate import AggregateRoot, AggregateSnapshot, ConcurrencyError
from .common.event import DomainEvent, EventMetadata, EventEnvelope
from .common.event_dispatcher import IEventDispatcher, EnhancedEventDispatcher

# Entities
from .entities.device import Device

# Value Objects
from .value_objects.equipment_code import EquipmentCode
from .value_objects.material_batch import MaterialBatch
from .value_objects.material_input import MaterialInput
from .value_objects.status_period import StatusPeriod
from .value_objects.time_range import TimeRange

# Enums
from .enums.machine_status import MachineStatus

# Events
from .events.device_events import StatusChangedEvent

# Exceptions
from .exceptions.base import DomainError
from .exceptions.domain_exceptions import (
    InvalidEquipmentCodeError,
    InvalidStatusTransitionError,
    InvalidTransitionError,
    DeviceNotFoundError,
    StaleDataError,
    InvalidTimeRangeError,
    StatusMergeError,
)

# Policies
from .policies.transition_policy import StatusTransitionPolicy

# Repository Interfaces
from .repositories.device_repository import DeviceRepository
from .repositories.production_repository import ProductionRepository

__all__ = [
    # Common
    "Entity",
    "TId",
    "ValueObject",
    "SingleValueObject",
    "AggregateRoot",
    "AggregateSnapshot",
    "ConcurrencyError",
    "DomainEvent",
    "EventMetadata",
    "EventEnvelope",
    "IEventDispatcher",
    "EnhancedEventDispatcher",
    # Entities
    "Device",
    # Value Objects
    "EquipmentCode",
    "MaterialBatch",
    "MaterialInput",
    "StatusPeriod",
    "TimeRange",
    # Enums
    "MachineStatus",
    # Events
    "StatusChangedEvent",
    # Exceptions
    "DomainError",
    "InvalidEquipmentCodeError",
    "InvalidStatusTransitionError",
    "InvalidTransitionError",
    "DeviceNotFoundError",
    "StaleDataError",
    "InvalidTimeRangeError",
    "StatusMergeError",
    # Policies
    "StatusTransitionPolicy",
    # Repositories
    "DeviceRepository",
    "ProductionRepository",
]
