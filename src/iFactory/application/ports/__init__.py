# application/ports/__init__.py
"""Application Ports - Interfaces for Infrastructure."""

from iFactory.application.ports.uow import AbstractUnitOfWork, AbstractUnitOfWorkFactory
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.ports.config import ISettingsManager

__all__ = [
    "AbstractUnitOfWork",
    "AbstractUnitOfWorkFactory",
    "IRemoteDataSource",
    "ICacheProvider",
    "ISettingsManager",
]
