"""
Application Port: Unit of Work Interface.
Defines the contract for transaction management.
"""

import abc
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from iFactory.domain.repositories.device_repository import DeviceRepository

    # Forward declaration for generic history repo if not explicitly imported
    # from iFactory.domain.repositories.production_repository import ProductionRepository


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries (Async Context Manager).
    Abstraction for Data Access Layer.
    """

    @property
    @abc.abstractmethod
    def devices(self) -> "DeviceRepository":
        """Repository for Device Aggregates (Hot Storage)."""
        pass

    @property
    @abc.abstractmethod
    def history(self) -> Any:
        """
        Repository for Device History/Production (Cold Storage).
        Returns domain repository interface.
        """
        pass

    @abc.abstractmethod
    async def __aenter__(self) -> "AbstractUnitOfWork":
        """Enter async context manager."""
        pass

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        pass

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit all changes."""
        pass

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes."""
        pass
