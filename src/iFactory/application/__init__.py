# src/iFactory/application/__init__.py
"""
Application Layer - Use Cases, Ports, and DTOs.

This layer contains:
- Use Cases (Commands and Queries)
- Application Services (Orchestration)
- DTOs (Data Transfer Objects)
- Ports (Interfaces for Infrastructure)
- Mediator Pattern Implementation

Architecture:
    Presentation -> Application -> Domain
                       |
                       v
                 Infrastructure (via Ports)
"""

# DTOs
from iFactory.application.common.dtos import (
    DeviceStatusDTO,
    DeviceDetailDTO,
    DeviceHistoryDTO,
    GanttSegmentDTO,
    TimelineDTO,
    SyncResultDTO,
    SyncStatusDTO,
    DeviceStatsDTO,
    DashboardSummaryDTO,
    PagedResultDTO,
)

# Exceptions
from iFactory.application.common.exceptions import (
    ApplicationException,
    ResourceNotFoundException,
    ResourceConflictException,
    RemoteSourceException,
    RemoteSourceUnavailableException,
    RemoteSourceTimeoutException,
    ValidationException,
    AuthorizationException,
    ConfigurationException,
    ConcurrencyException,
)

# Ports
from iFactory.application.ports.uow import (
    AbstractUnitOfWork,
    AbstractUnitOfWorkFactory,
)
from iFactory.application.ports.remote import (
    IRemoteDataSource,
    ConnectionState,
    RemoteHealthStatus,
    RemoteMetrics,
)
from iFactory.application.ports.cache import (
    ICacheProvider,
    IDistributedCache,
    CacheStatistics,
)
from iFactory.application.ports.config import ISettingsManager

# Mediator
from iFactory.application.mediator import (
    Mediator,
    IMediator,
    get_mediator,
    Command,
    Query,
    IRequest,
    IRequestHandler,
)

__all__ = [
    # DTOs
    "DeviceStatusDTO",
    "DeviceDetailDTO",
    "DeviceHistoryDTO",
    "GanttSegmentDTO",
    "TimelineDTO",
    "SyncResultDTO",
    "SyncStatusDTO",
    "DeviceStatsDTO",
    "DashboardSummaryDTO",
    "PagedResultDTO",
    # Exceptions
    "ApplicationException",
    "ResourceNotFoundException",
    "ResourceConflictException",
    "RemoteSourceException",
    "RemoteSourceUnavailableException",
    "RemoteSourceTimeoutException",
    "ValidationException",
    "AuthorizationException",
    "ConfigurationException",
    "ConcurrencyException",
    # Ports
    "AbstractUnitOfWork",
    "AbstractUnitOfWorkFactory",
    "IRemoteDataSource",
    "ConnectionState",
    "RemoteHealthStatus",
    "RemoteMetrics",
    "ICacheProvider",
    "IDistributedCache",
    "CacheStatistics",
    "ISettingsManager",
    # Mediator
    "Mediator",
    "IMediator",
    "get_mediator",
    "Command",
    "Query",
    "IRequest",
    "IRequestHandler",
]
