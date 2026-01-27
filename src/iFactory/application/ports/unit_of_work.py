from abc import ABC, abstractmethod
from typing import Optional

from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.repositories.production_repository import ProductionRepository


class AbstractUnitOfWork(ABC):
    """
    Abstract Unit of Work.
    Manages transaction boundaries and provides access to Repositories.
    """

    devices: DeviceRepository
    production: ProductionRepository

    @abstractmethod
    async def __aenter__(self) -> "AbstractUnitOfWork":
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commits the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rolls back the current transaction."""
        pass
