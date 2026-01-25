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
from .interfaces.cache_provider import ICacheProvider  # Đã sửa thành ICacheProvider

# 3. Mappers
from .mappers.device_mapper import to_device_status_dto

# 4. Use Cases (Interactors)
from .use_cases.device.get_all_devices_status import GetAllDevicesStatusUseCase
from .use_cases.device.sync_device_status import SyncDeviceStatusUseCase

# 5. Application Exceptions
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
    "ICacheProvider",  # Đã sửa thành ICacheProvider
    # Mappers
    "to_device_status_dto",
    # Use Cases
    "GetAllDevicesStatusUseCase",
    "SyncDeviceStatusUseCase",
    # Exceptions
    "ApplicationException",
    "ResourceNotFoundException",
    "UnauthorizedActionException",
    "DomainConstraintViolationException",
]
