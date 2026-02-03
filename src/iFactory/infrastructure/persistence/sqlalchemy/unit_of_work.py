# File: infrastructure/persistence/sqlalchemy/unit_of_work.py
"""
Infrastructure: Unit of Work with Domain Event Support.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, List, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from iFactory.application.ports.uow import AbstractUnitOfWork, EventDispatchCallback
from iFactory.domain.common.aggregate import AggregateRoot
from iFactory.domain.common.event import DomainEvent
from iFactory.infrastructure.persistence.sqlalchemy.repositories.device_repository import (
    SqlAlchemyDeviceRepository,
)
from iFactory.infrastructure.persistence.sqlalchemy.repositories.production_repository import (
    SqlAlchemyProductionRepository,
)

logger = logging.getLogger(__name__)


class StorageUnitOfWork(AbstractUnitOfWork):
    """
    Single storage unit of work with domain event support.

    Features:
    - Automatic rollback on exception
    - Safe commit with rollback on failure
    - Domain event collection and dispatch after commit
    - Proper resource cleanup
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._devices_repo: Optional[SqlAlchemyDeviceRepository] = None
        self._history_repo: Optional[SqlAlchemyProductionRepository] = None
        self._committed = False
        self._rolled_back = False

        # Domain event support
        self._tracked_aggregates: List[AggregateRoot] = []
        self._event_dispatcher: Optional[EventDispatchCallback] = None

    @property
    def devices(self) -> Optional[SqlAlchemyDeviceRepository]:
        return self._devices_repo

    @property
    def history(self) -> Optional[SqlAlchemyProductionRepository]:
        return self._history_repo

    @property
    def session(self) -> Optional[AsyncSession]:
        """Expose session for advanced scenarios (use sparingly)."""
        return self._session

    def track_aggregate(self, aggregate: AggregateRoot) -> None:
        """
        Track an aggregate for domain event collection.

        Events will be collected after successful commit.
        """
        if aggregate not in self._tracked_aggregates:
            self._tracked_aggregates.append(aggregate)

    def set_event_dispatcher(self, callback: EventDispatchCallback) -> None:
        """Set the callback for dispatching events after commit."""
        self._event_dispatcher = callback

    async def __aenter__(self) -> "StorageUnitOfWork":
        if self._session is not None:
            raise RuntimeError("UnitOfWork already entered. Cannot reuse.")

        self._session = self._session_factory()
        self._devices_repo = SqlAlchemyDeviceRepository(self._session)
        self._history_repo = SqlAlchemyProductionRepository(self._session)
        self._committed = False
        self._rolled_back = False
        self._tracked_aggregates.clear()

        logger.debug("UnitOfWork started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager with proper cleanup."""
        try:
            if exc_type is not None:
                logger.warning("UnitOfWork exiting with exception: %s: %s", exc_type.__name__ if exc_type else "Unknown", exc_val)
                await self._safe_rollback()
            elif not self._committed and not self._rolled_back:
                logger.warning("UnitOfWork exiting without explicit commit/rollback. " "Rolling back as safety measure.")
                await self._safe_rollback()
        finally:
            await self._cleanup()

        return None

    async def commit(self) -> None:
        """
        Commit all pending changes and dispatch domain events.

        Events are only dispatched after successful commit to ensure
        consistency - we don't want to notify about changes that were
        rolled back.
        """
        self._ensure_active()

        if self._committed:
            logger.warning("UnitOfWork.commit() called but already committed")
            return

        if self._rolled_back:
            raise RuntimeError("Cannot commit after rollback")

        try:
            await self._session.commit()
            self._committed = True
            logger.debug("UnitOfWork committed successfully")

            # Dispatch domain events AFTER successful commit
            await self._dispatch_domain_events()

        except SQLAlchemyError as e:
            logger.error("UnitOfWork commit failed: %s. Rolling back.", e)
            await self._safe_rollback()
            raise

    async def _dispatch_domain_events(self) -> None:
        """Collect and dispatch domain events from tracked aggregates."""
        if not self._event_dispatcher:
            # No dispatcher configured - just clear events
            for aggregate in self._tracked_aggregates:
                aggregate.clear_events()
            return

        # Collect all events from tracked aggregates
        all_events: List[DomainEvent] = []
        for aggregate in self._tracked_aggregates:
            events = aggregate.collect_events()
            all_events.extend(events)

        if not all_events:
            return

        logger.debug("Dispatching %d domain events", len(all_events))

        try:
            await self._event_dispatcher(all_events)
        except Exception as e:
            # Log but don't fail the commit - events are best-effort
            logger.error("Failed to dispatch domain events: %s", e)

    async def rollback(self) -> None:
        """Rollback all pending changes and clear events."""
        if self._session is None:
            return

        if self._rolled_back:
            return

        # Clear events on rollback - they shouldn't be dispatched
        for aggregate in self._tracked_aggregates:
            aggregate.clear_events()

        await self._safe_rollback()

    async def _safe_rollback(self) -> None:
        """Internal rollback that handles errors gracefully."""
        if self._session is None or self._rolled_back:
            return

        try:
            await self._session.rollback()
            self._rolled_back = True
            logger.debug("UnitOfWork rolled back")
        except SQLAlchemyError as e:
            logger.error("UnitOfWork rollback failed: %s", e)
            self._rolled_back = True

    async def _cleanup(self) -> None:
        """Clean up session and repositories."""
        if self._session:
            try:
                await self._session.close()
                logger.debug("UnitOfWork session closed")
            except Exception as e:
                logger.error("Error closing session: %s", e)
            finally:
                self._session = None

        self._devices_repo = None
        self._history_repo = None
        self._tracked_aggregates.clear()

    def _ensure_active(self) -> None:
        """Ensure session is active."""
        if self._session is None:
            raise RuntimeError("UnitOfWork session is not active. " "Use 'async with uow:' context manager.")


# Legacy compatibility aliases
HotStorageUnitOfWork = StorageUnitOfWork
ColdStorageUnitOfWork = StorageUnitOfWork
DualStorageUnitOfWork = StorageUnitOfWork
SqlAlchemyUnitOfWork = StorageUnitOfWork


__all__ = [
    "StorageUnitOfWork",
    "HotStorageUnitOfWork",
    "ColdStorageUnitOfWork",
    "DualStorageUnitOfWork",
    "SqlAlchemyUnitOfWork",
]
