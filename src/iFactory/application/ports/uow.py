"""
Application Port: Unit of Work Interface.
Defines the contract for transaction management.
"""

import abc
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from iFactory.domain.repositories.device_repository import DeviceRepository


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries (Async Context Manager).
    """

    @property
    @abc.abstractmethod
    def devices(self) -> Optional["DeviceRepository"]:
        """Repository for Device cache (optional in remote-first)."""
        pass

    @property
    @abc.abstractmethod
    def history(self) -> Optional[Any]:
        """Repository for history/production data."""
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
