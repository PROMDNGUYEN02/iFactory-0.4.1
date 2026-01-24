"""
Domain Layer Package.

Contains core business logic, entities, value objects, and repository interfaces.
This layer has NO dependencies on other layers.
"""

from __future__ import annotations

# ====== ENTITIES ======
from .entities import Device

# ====== DOMAIN EVENTS ======
from .events import StatusChangedEvent, DomainEvent

# ====== ENUMS ======
from .enums import DeviceStatus, StatusCode

# ====== VALUE OBJECTS ======
from .value_objects import EquipmentCode, DeviceHistory, MaterialInput, Status, SyncMetadata, TimeRange

# ====== DOMAIN SERVICES ======
from .services import StatusNormalizationService

# ====== REPOSITORIES ======
from .repositories import (
    DeviceRepository,
    StatusRepository,
    InputRepository,
    SyncMetadataRepository,
)

# ====== EXCEPTIONS ======
from .exceptions import (
    DomainError,
    DeviceError,
    DeviceNotFoundError,
    InvalidStatusError,
    InvalidDeviceStateError,
    InvalidEquipmentCodeError,
    InvalidTimeRangeError,
    HistoryMergeError,
    ValidationError,
    RepositoryError,
)

__all__ = [
    # Entities
    "Device",
    # Domain Events
    "StatusChangedEvent",
    "DomainEvent",
    # Enums
    "DeviceStatus",
    "StatusCode",
    # Value Objects
    "EquipmentCode",
    "DeviceHistory",
    "MaterialInput",
    "Status",
    "SyncMetadata",
    "TimeRange",
    # Repositories
    "DeviceRepository",
    "StatusRepository",
    "InputRepository",
    "SyncMetadataRepository",
    # Exceptions
    "DomainError",
    "DeviceError",
    "DeviceNotFoundError",
    "InvalidStatusError",
    "InvalidDeviceStateError",
    "InvalidEquipmentCodeError",
    "InvalidTimeRangeError",
    "HistoryMergeError",
    "ValidationError",
    "RepositoryError",
]
