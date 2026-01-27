"""
iFactory Domain Core.

This module encapsulates the pure business logic and invariants of the application.
It has zero dependencies on external frameworks, databases, UI components, or IO operations.
All logic is expressed in ubiquitous business language.
"""

from .entities import AggregateRoot, Device
from .enums import MachineStatus
from .events import DomainEvent, StatusChangedEvent
from .exceptions import (
    DomainError,
    InvalidEquipmentCodeError,
    InvalidStatusTransitionError,
    InvalidTimeRangeError,
    StatusMergeError,
)
from .policies import StatusTransitionPolicy
from .repositories import DeviceRepository, ProductionRepository
from .value_objects import (
    EquipmentCode,
    MaterialBatch,
    MaterialInput,
    StatusPeriod,
    TimeRange,
)

__version__ = "0.4.1"

__all__ = [
    "AggregateRoot",
    "Device",
    "MachineStatus",
    "DomainEvent",
    "StatusChangedEvent",
    "DomainError",
    "InvalidEquipmentCodeError",
    "InvalidStatusTransitionError",
    "InvalidTimeRangeError",
    "StatusMergeError",
    "StatusTransitionPolicy",
    "DeviceRepository",
    "ProductionRepository",
    "EquipmentCode",
    "MaterialBatch",
    "MaterialInput",
    "StatusPeriod",
    "TimeRange",
]
