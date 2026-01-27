"""
iFactory Domain Core.

This module encapsulates the pure business logic and invariants of the application.
It has zero dependencies on external frameworks, databases, UI components, or IO operations.
All logic is expressed in ubiquitous business language.
"""

from .entities.aggregate_root import AggregateRoot
from .entities.device import Device
from .enums.machine_status import MachineStatus
from .events.base import DomainEvent
from .events.device_events import StatusChangedEvent
from .exceptions.base import DomainError
from .exceptions.device_exceptions import (
    DeviceNotFoundError,
    InvalidEquipmentCodeError,
    InvalidStatusTransitionError,
)
from .exceptions.time_exceptions import (
    InvalidTimeRangeError,
    StatusMergeError,
)
from .policies.status_transition_policy import StatusTransitionPolicy
from .repositories.device_repository import DeviceRepository
from .repositories.production_repository import ProductionRepository
from .value_objects.equipment_code import EquipmentCode
from .value_objects.material_batch import MaterialBatch
from .value_objects.material_input import MaterialInput
from .value_objects.status_period import StatusPeriod
from .value_objects.time_range import TimeRange

__version__ = "0.5.0"

__all__ = [
    "AggregateRoot",
    "Device",
    "MachineStatus",
    "DomainEvent",
    "StatusChangedEvent",
    "DomainError",
    "DeviceNotFoundError",
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
