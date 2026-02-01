# application/__init__.py
"""Application Layer - Use Cases, Ports, and DTOs."""

from iFactory.application.common.dtos import (
    DeviceStatusDTO,
    DeviceHistoryDTO,
    GanttSegmentDTO,
)
from iFactory.application.common.exceptions import (
    ApplicationException,
    ResourceNotFoundException,
    RemoteSourceException,
)
from iFactory.application.ports.uow import AbstractUnitOfWork, AbstractUnitOfWorkFactory
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.ports.config import ISettingsManager

__all__ = [
    # DTOs
    "DeviceStatusDTO",
    "DeviceHistoryDTO",
    "GanttSegmentDTO",
    # Exceptions
    "ApplicationException",
    "ResourceNotFoundException",
    "RemoteSourceException",
    # Ports
    "AbstractUnitOfWork",
    "AbstractUnitOfWorkFactory",
    "IRemoteDataSource",
    "ICacheProvider",
    "ISettingsManager",
]
