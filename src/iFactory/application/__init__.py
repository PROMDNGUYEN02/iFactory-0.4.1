"""
Application Layer Package.

Entry point for the business logic layer. Exports Use Cases, DTOs,
and Facade Services required by the Presentation Layer.
"""

from .dto import DeviceStatusDTO, GanttSegmentDTO
from .interfaces import (
    CacheProvider,
    RemoteDataSource,
    RemoteInputRecord,
    RemoteStatusRecord,
    UnitOfWork,
)
from .use_cases import (
    GenerateProductionTimelineUseCase,
    GetAllDevicesStatusUseCase,
    GetDeviceHistoryUseCase,
    GetLatestDeviceStatusUseCase,
    SyncDeviceStatusUseCase,
)

# Facade Services for backward compatibility / specific UI needs
from .services import RightMenuDataProvider, SummaryDataProvider
from .facades import DeviceFacade
from .view_models import DeviceViewModel
from .services import StatusUIMapper

__all__ = [
    "DeviceStatusDTO",
    "GanttSegmentDTO",
    "CacheProvider",
    "RemoteDataSource",
    "RemoteInputRecord",
    "RemoteStatusRecord",
    "UnitOfWork",
    # Use Cases
    "GenerateProductionTimelineUseCase",
    "GetAllDevicesStatusUseCase",
    "GetDeviceHistoryUseCase",
    "GetLatestDeviceStatusUseCase",
    "SyncDeviceStatusUseCase",
    # Services
    "RightMenuDataProvider",
    "SummaryDataProvider",
    # Facades (Clean Architecture entry points)
    "DeviceFacade",
    "StatusUIMapper",
    # View Models (UI-specific data formats)
    "DeviceViewModel",
]
