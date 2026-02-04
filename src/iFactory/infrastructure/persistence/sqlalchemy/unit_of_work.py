# src/iFactory/infrastructure/persistence/sqlalchemy/unit_of_work.py
"""
Infrastructure: Unit of Work with Domain Event Support.

Features:
- Transaction management with async context manager
- Domain event collection and dispatch after commit
- Automatic rollback on exception
- Proper resource cleanup
- Nested transaction support (savepoints)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional, Callable, List, Awaitable, TypeVar, Generic

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

T = TypeVar("T")


class StorageUnitOfWork(AbstractUnitOfWork):
    """
    Single storage unit of work with domain event support.

    Features:
    - Automatic rollback on exception
    - Safe commit with rollback on failure
    - Domain event collection and dispatch after commit
    - Proper resource cleanup
    - Tracks aggregates for event collection

    Usage:
        async with uow_factory() as uow:
            device = await uow.devices.get(code)
            device.update_status(new_status)
            uow.track_aggregate(device)
            await uow.devices.save(device)
            await uow.commit()
    """

    __slots__ = (
        "_session_factory",
        "_session",
        "_devices_repo",
        "_history_repo",
        "_committed",
        "_rolled_back",
        "_tracked_aggregates",
        "_event_dispatcher",
        "_in_transaction",
    )

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """
        Initialize UnitOfWork.

        Args:
            session_factory: Factory function that creates AsyncSession instances
        """
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._devices_repo: Optional[SqlAlchemyDeviceRepository] = None
        self._history_repo: Optional[SqlAlchemyProductionRepository] = None
        self._committed = False
        self._rolled_back = False
        self._in_transaction = False

        # Domain event support
        self._tracked_aggregates: List[AggregateRoot] = []
        self._event_dispatcher: Optional[EventDispatchCallback] = None

    # ========================================================================
    # Repository Properties
    # ========================================================================

    @property
    def devices(self) -> Optional[SqlAlchemyDeviceRepository]:
        """Device repository."""
        return self._devices_repo

    @property
    def history(self) -> Optional[SqlAlchemyProductionRepository]:
        """Production history repository."""
        return self._history_repo

    @property
    def session(self) -> Optional[AsyncSession]:
        """
        Expose session for advanced scenarios.

        Use sparingly - prefer repository methods.
        """
        return self._session

    @property
    def is_active(self) -> bool:
        """Check if UoW is in an active transaction."""
        return self._session is not None and self._in_transaction

    # ========================================================================
    # Domain Event Support
    # ========================================================================

    def track_aggregate(self, aggregate: AggregateRoot) -> None:
        """
        Track an aggregate for domain event collection.

        Events will be collected from tracked aggregates after
        successful commit and dispatched via the event callback.

        Args:
            aggregate: Aggregate root to track
        """
        if aggregate not in self._tracked_aggregates:
            self._tracked_aggregates.append(aggregate)
            logger.debug(
                "Tracking aggregate: %s[%s]",
                type(aggregate).__name__,
                aggregate.aggregate_id,
            )

    def untrack_aggregate(self, aggregate: AggregateRoot) -> None:
        """Remove aggregate from tracking."""
        if aggregate in self._tracked_aggregates:
            self._tracked_aggregates.remove(aggregate)

    def set_event_dispatcher(self, callback: EventDispatchCallback) -> None:
        """
        Set the callback for dispatching events after commit.

        Args:
            callback: Async function that receives list of domain events
        """
        self._event_dispatcher = callback

    # ========================================================================
    # Context Manager
    # ========================================================================

    async def __aenter__(self) -> "StorageUnitOfWork":
        """Enter async context manager, begin transaction."""
        if self._session is not None:
            raise RuntimeError("UnitOfWork already entered. Cannot reuse - create a new instance.")

        self._session = self._session_factory()
        self._devices_repo = SqlAlchemyDeviceRepository(self._session)
        self._history_repo = SqlAlchemyProductionRepository(self._session)
        self._committed = False
        self._rolled_back = False
        self._in_transaction = True
        self._tracked_aggregates.clear()

        logger.debug("UnitOfWork started")
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Exit async context manager with proper cleanup."""
        try:
            if exc_type is not None:
                # Exception occurred - rollback
                logger.warning(
                    "UnitOfWork exiting with exception: %s: %s",
                    exc_type.__name__ if exc_type else "Unknown",
                    exc_val,
                )
                await self._safe_rollback()
            elif not self._committed and not self._rolled_back:
                # No explicit commit/rollback - rollback for safety
                logger.warning("UnitOfWork exiting without explicit commit/rollback. " "Rolling back as safety measure.")
                await self._safe_rollback()
        finally:
            await self._cleanup()

        # Don't suppress exceptions
        return None

    # ========================================================================
    # Transaction Control
    # ========================================================================

    async def commit(self) -> None:
        """
        Commit all pending changes and dispatch domain events.

        Events are only dispatched after successful commit to ensure
        consistency - we don't want to notify about changes that were
        rolled back.

        Raises:
            RuntimeError: If already committed or rolled back
            SQLAlchemyError: If commit fails (will auto-rollback)
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
            self._in_transaction = False
            logger.debug("UnitOfWork committed successfully")

            # Dispatch domain events AFTER successful commit
            await self._dispatch_domain_events()

        except SQLAlchemyError as e:
            logger.error("UnitOfWork commit failed: %s. Rolling back.", e)
            await self._safe_rollback()
            raise

    async def rollback(self) -> None:
        """
        Rollback all pending changes and clear events.

        Safe to call multiple times - subsequent calls are no-ops.
        """
        if self._session is None:
            return

        if self._rolled_back:
            return

        # Clear events on rollback - they shouldn't be dispatched
        for aggregate in self._tracked_aggregates:
            aggregate.clear_events()

        await self._safe_rollback()

    async def flush(self) -> None:
        """
        Flush pending changes to database without committing.

        Useful for getting generated IDs before commit.
        """
        self._ensure_active()
        await self._session.flush()

    # ========================================================================
    # Event Dispatching
    # ========================================================================

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
            logger.debug("Domain events dispatched successfully")
        except Exception as e:
            # Log but don't fail the commit - events are best-effort
            logger.error("Failed to dispatch domain events: %s", e)

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    async def _safe_rollback(self) -> None:
        """Internal rollback that handles errors gracefully."""
        if self._session is None or self._rolled_back:
            return

        try:
            await self._session.rollback()
            self._rolled_back = True
            self._in_transaction = False
            logger.debug("UnitOfWork rolled back")
        except SQLAlchemyError as e:
            logger.error("UnitOfWork rollback failed: %s", e)
            self._rolled_back = True
            self._in_transaction = False

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
        self._in_transaction = False

    def _ensure_active(self) -> None:
        """Ensure session is active."""
        if self._session is None:
            raise RuntimeError("UnitOfWork session is not active. " "Use 'async with uow:' context manager.")
        if not self._in_transaction:
            raise RuntimeError("UnitOfWork is not in a transaction. " "Transaction may have been committed or rolled back.")


class UnitOfWorkFactory:
    """
    Factory for creating UnitOfWork instances.

    Provides a clean interface for dependency injection.
    """

    __slots__ = ("_session_factory", "_event_dispatcher")

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        event_dispatcher: Optional[EventDispatchCallback] = None,
    ) -> None:
        """
        Initialize factory.

        Args:
            session_factory: Factory for creating database sessions
            event_dispatcher: Optional callback for domain events
        """
        self._session_factory = session_factory
        self._event_dispatcher = event_dispatcher

    def __call__(self) -> StorageUnitOfWork:
        """Create a new UnitOfWork instance."""
        uow = StorageUnitOfWork(self._session_factory)
        if self._event_dispatcher:
            uow.set_event_dispatcher(self._event_dispatcher)
        return uow

    def set_event_dispatcher(self, callback: EventDispatchCallback) -> None:
        """Update the event dispatcher for future UoW instances."""
        self._event_dispatcher = callback


# ============================================================================
# Scoped UnitOfWork for nested transactions
# ============================================================================


class ScopedUnitOfWork:
    """
    Scoped UnitOfWork that supports savepoints for nested transactions.

    Usage:
        async with uow_factory() as uow:
            # Outer transaction
            await uow.devices.save(device1)

            async with uow.scope() as nested:
                # Nested savepoint
                await nested.devices.save(device2)
                # Can rollback just this scope
                if error:
                    await nested.rollback()

            await uow.commit()  # Commits device1, device2 only if nested committed
    """

    __slots__ = ("_parent", "_savepoint_name", "_committed", "_rolled_back")

    def __init__(self, parent: StorageUnitOfWork, savepoint_name: str) -> None:
        self._parent = parent
        self._savepoint_name = savepoint_name
        self._committed = False
        self._rolled_back = False

    @property
    def devices(self):
        return self._parent.devices

    @property
    def history(self):
        return self._parent.history

    async def __aenter__(self) -> "ScopedUnitOfWork":
        # Begin savepoint
        await self._parent.session.begin_nested()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and not self._rolled_back:
            await self.rollback()

    async def commit(self) -> None:
        """Commit this savepoint."""
        if not self._committed and not self._rolled_back:
            # Savepoints don't need explicit commit in SQLAlchemy
            self._committed = True

    async def rollback(self) -> None:
        """Rollback to this savepoint."""
        if not self._rolled_back:
            await self._parent.session.rollback()
            self._rolled_back = True


# Add scope method to StorageUnitOfWork
def _scope(self, name: str = "savepoint") -> ScopedUnitOfWork:
    """Create a nested scope (savepoint)."""
    return ScopedUnitOfWork(self, name)


StorageUnitOfWork.scope = _scope


# ============================================================================
# Legacy compatibility aliases
# ============================================================================

HotStorageUnitOfWork = StorageUnitOfWork
ColdStorageUnitOfWork = StorageUnitOfWork
DualStorageUnitOfWork = StorageUnitOfWork
SqlAlchemyUnitOfWork = StorageUnitOfWork


__all__ = [
    "StorageUnitOfWork",
    "UnitOfWorkFactory",
    "ScopedUnitOfWork",
    # Legacy aliases
    "HotStorageUnitOfWork",
    "ColdStorageUnitOfWork",
    "DualStorageUnitOfWork",
    "SqlAlchemyUnitOfWork",
]
