# File: application/ports/uow.py
"""
Application Port: Unit of Work Interface.

Defines the contract for transaction management following the Unit of Work pattern.
This port ensures the Application Layer remains independent of persistence details.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional, TypeVar, Generic

if TYPE_CHECKING:
    from iFactory.domain.repositories.device_repository import AbstractDeviceRepository
    from iFactory.domain.repositories.production_repository import AbstractProductionRepository


T = TypeVar("T")


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries.

    Implements the Unit of Work pattern as an async context manager.
    All repository access should go through the UoW to ensure
    transactional consistency.

    Usage:
        async with uow_factory() as uow:
            device = await uow.devices.get(code)
            device.update_status(new_status)
            await uow.devices.save(device)
            await uow.commit()
    """

    devices: Optional["AbstractDeviceRepository"]
    history: Optional["AbstractProductionRepository"]

    @abc.abstractmethod
    async def __aenter__(self) -> "AbstractUnitOfWork":
        """Enter async context manager, begin transaction."""
        raise NotImplementedError

    @abc.abstractmethod
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Exit async context manager, rollback on exception."""
        raise NotImplementedError

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit all pending changes."""
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback all pending changes."""
        raise NotImplementedError


class AbstractUnitOfWorkFactory(abc.ABC):
    """
    Factory for creating Unit of Work instances.

    This abstraction allows the Application Layer to request new
    UoW instances without knowing the concrete implementation.
    """

    @abc.abstractmethod
    def __call__(self) -> AbstractUnitOfWork:
        """Create a new Unit of Work instance."""
        raise NotImplementedError


__all__ = ["AbstractUnitOfWork", "AbstractUnitOfWorkFactory"]
