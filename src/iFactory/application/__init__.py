"""
Application Layer Package.

Entry point for the application orchestration layer.
Exports Use Cases, DTOs, and Interfaces required by other layers.
NOTE: UI logic (View Models, Facades, UI Mappers) has been moved to the Presentation layer.
"""

# 1. DTOs (Pure Data Transfer Objects)
from .dtos.device_dtos import DeviceStatusDTO, GanttSegmentDTO
from .dtos.pagination import PaginatedResponseDTO

# 2. Interfaces (Ports)
from .interfaces.unit_of_work import IUnitOfWork
from .interfaces.repository import IRepository
from .interfaces.logger import ILogger
from .interfaces.cache_provider import CacheProvider

# 3. Use Cases (Interactors) - Add your specific device use cases here
from .use_cases.device.get_all_devices_status import GetAllDevicesStatusUseCase
from .use_cases.device.sync_device_status import SyncDeviceStatusUseCase

# 4. Application Exceptions
from .exceptions import ApplicationException, ResourceNotFoundException, UnauthorizedActionException, DomainConstraintViolationException

__all__ = [
    # DTOs
    "DeviceStatusDTO",
    "GanttSegmentDTO",
    "PaginatedResponseDTO",
    # Interfaces
    "IUnitOfWork",
    "IRepository",
    "ILogger",
    "CacheProvider",
    # Use Cases
    "GetAllDevicesStatusUseCase",
    "SyncDeviceStatusUseCase",
    # Exceptions
    "ApplicationException",
    "ResourceNotFoundException",
    "UnauthorizedActionException",
    "DomainConstraintViolationException",
]
