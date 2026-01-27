"""
Application Port: Unit of Work Interface.
Defines async transaction management interface for Infrastructure layer.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iFactory.domain.repositories.device_repository import DeviceRepository


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries (Async Context Manager).
    Ensures data integrity (ACID) for database operations.
    """

    devices: "DeviceRepository"

    @abc.abstractmethod
    async def __aenter__(self) -> "AbstractUnitOfWork":
        """Enter async context manager."""
        pass

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager, handle rollback on error."""
        pass

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit all changes to the database."""
        pass

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback all changes on error."""
        pass
