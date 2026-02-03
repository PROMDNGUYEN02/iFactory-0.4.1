# File: application/ports/uow.py (Updated)
"""
Application Port: Unit of Work Interface.

Enhanced with domain event collection and dispatch support.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional, List, Callable, Awaitable

if TYPE_CHECKING:
    from iFactory.domain.repositories.device_repository import DeviceRepository
    from iFactory.domain.repositories.production_repository import ProductionRepository
    from iFactory.domain.common.event import DomainEvent


# Type alias for event dispatcher callback
EventDispatchCallback = Callable[[List["DomainEvent"]], Awaitable[None]]


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries.

    Implements the Unit of Work pattern as an async context manager.
    All repository access should go through the UoW to ensure
    transactional consistency.

    Event Dispatching:
        UoW can optionally dispatch domain events after successful commit.
        Register aggregates via track_aggregate() and events will be
        collected and dispatched automatically.

    Usage:
        async with uow_factory() as uow:
            device = await uow.devices.get(code)
            device.update_status(new_status)
            uow.track_aggregate(device)  # Track for event collection
            await uow.devices.save(device)
            await uow.commit()  # Events dispatched after successful commit
    """

    devices: Optional["DeviceRepository"]
    history: Optional["ProductionRepository"]

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

    def track_aggregate(self, aggregate) -> None:
        """
        Track an aggregate for domain event collection.

        Events will be collected from tracked aggregates after
        successful commit and dispatched via the event callback.

        Default implementation does nothing - override in concrete class.
        """
        pass

    def set_event_dispatcher(self, callback: EventDispatchCallback) -> None:
        """
        Set callback for event dispatching after commit.

        Default implementation does nothing - override in concrete class.
        """
        pass


class AbstractUnitOfWorkFactory(abc.ABC):
    """Factory for creating Unit of Work instances."""

    @abc.abstractmethod
    def __call__(self) -> AbstractUnitOfWork:
        """Create a new Unit of Work instance."""
        raise NotImplementedError


__all__ = ["AbstractUnitOfWork", "AbstractUnitOfWorkFactory", "EventDispatchCallback"]
