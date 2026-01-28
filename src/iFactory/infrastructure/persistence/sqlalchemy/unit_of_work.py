"""
Infrastructure: Unit of Work.
Manages atomic transactions for Hot and Cold stores.
"""

from __future__ import annotations

from typing import Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.application.ports.unit_of_work import AbstractUnitOfWork

# FIXED: Import from correct files (device_repository, production_repository)
# Alias them to Hot/Cold Repository for internal consistency
from iFactory.infrastructure.persistence.sqlalchemy.repositories.device_repository import SqlAlchemyDeviceRepository as HotRepository
from iFactory.infrastructure.persistence.sqlalchemy.repositories.production_repository import SqlAlchemyProductionRepository as ColdRepository


class HotStorageUnitOfWork(AbstractUnitOfWork):
    """Transaction manager for Hot Store."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self.devices: Optional[HotRepository] = None

    async def __aenter__(self) -> "HotStorageUnitOfWork":
        self._session = self._session_factory()
        self.devices = HotRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None
        self.devices = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


class ColdStorageUnitOfWork(AbstractUnitOfWork):
    """Transaction manager for Cold Store."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self.history: Optional[ColdRepository] = None

    async def __aenter__(self) -> "ColdStorageUnitOfWork":
        self._session = self._session_factory()
        self.history = ColdRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None
        self.history = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


class DualStorageUnitOfWork:
    """
    Orchestrates transactions across both Hot and Cold stores.
    Used when syncing data from remote to local.
    """

    def __init__(self, hot_session_factory: Callable[[], AsyncSession], cold_session_factory: Callable[[], AsyncSession]) -> None:
        self._hot_session_factory = hot_session_factory
        self._cold_session_factory = cold_session_factory
        self._hot_session: Optional[AsyncSession] = None
        self._cold_session: Optional[AsyncSession] = None

        # Public Repositories
        self.devices: Optional[HotRepository] = None
        self.history: Optional[ColdRepository] = None

    async def __aenter__(self) -> "DualStorageUnitOfWork":
        self._hot_session = self._hot_session_factory()
        self._cold_session = self._cold_session_factory()

        self.devices = HotRepository(self._hot_session)
        self.history = ColdRepository(self._cold_session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._hot_session:
            await self._hot_session.close()
        if self._cold_session:
            await self._cold_session.close()

        self._hot_session = None
        self._cold_session = None
        self.devices = None
        self.history = None

    async def commit(self) -> None:
        """Atomic-like commit (best effort)."""
        if self._hot_session:
            await self._hot_session.commit()
        if self._cold_session:
            await self._cold_session.commit()

    async def rollback(self) -> None:
        """Rollback both sessions."""
        if self._hot_session:
            await self._hot_session.rollback()
        if self._cold_session:
            await self._cold_session.rollback()


# Compatibility Aliases
SqlAlchemyUnitOfWork = HotStorageUnitOfWork
HotStorageRepository = HotRepository
ColdStorageRepository = ColdRepository
