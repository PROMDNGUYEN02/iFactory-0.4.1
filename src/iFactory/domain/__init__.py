"""
iFactory Domain Layer
Pure business logic core. No infrastructure or UI dependencies allowed.
"""

from .common.aggregate import AggregateRoot
from .common.event import DomainEvent
from .entities.device import Device
from .enums.machine_status import MachineStatus
from .events.device_events import StatusChangedEvent
from .exceptions.base import DomainError
from .policies.transition_policy import StatusTransitionPolicy
from .repositories.device_repository import DeviceRepository
from .repositories.production_repository import ProductionRepository
from .value_objects.equipment_code import EquipmentCode
from .value_objects.material_batch import MaterialBatch
from .value_objects.material_input import MaterialInput
from .value_objects.status_period import StatusPeriod
from .value_objects.time_range import TimeRange

__all__ = [
    # Common
    "AggregateRoot",
    "DomainEvent",
    # Entities
    "Device",
    # Enums
    "MachineStatus",
    # Events
    "StatusChangedEvent",
    # Exceptions
    "DomainError",
    # Policies
    "StatusTransitionPolicy",
    # Repositories (Interfaces)
    "DeviceRepository",
    "ProductionRepository",
    # Value Objects
    "EquipmentCode",
    "MaterialBatch",
    "MaterialInput",
    "StatusPeriod",
    "TimeRange",
]
