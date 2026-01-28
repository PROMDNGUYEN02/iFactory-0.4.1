"""
Infrastructure: Unit of Work.
Manages atomic transactions for Hot and Cold stores.
"""

from __future__ import annotations

from typing import Optional, Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.application.ports.uow import AbstractUnitOfWork

from iFactory.infrastructure.persistence.sqlalchemy.repositories.device_repository import SqlAlchemyDeviceRepository as HotRepository
from iFactory.infrastructure.persistence.sqlalchemy.repositories.production_repository import SqlAlchemyProductionRepository as ColdRepository


class HotStorageUnitOfWork(AbstractUnitOfWork):
    """Transaction manager for Hot Store (Latest State)."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._devices_repo: Optional[HotRepository] = None

    @property
    def devices(self) -> Optional[HotRepository]:
        return self._devices_repo

    @property
    def history(self) -> None:
        """Hot storage does not have history."""
        return None

    async def __aenter__(self) -> "HotStorageUnitOfWork":
        self._session = self._session_factory()
        self._devices_repo = HotRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None
        self._devices_repo = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


class ColdStorageUnitOfWork(AbstractUnitOfWork):
    """Transaction manager for Cold Store (History)."""

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._history_repo: Optional[ColdRepository] = None

    @property
    def devices(self) -> None:
        """Cold storage does not have active device state."""
        return None

    @property
    def history(self) -> Optional[ColdRepository]:
        return self._history_repo

    async def __aenter__(self) -> "ColdStorageUnitOfWork":
        self._session = self._session_factory()
        self._history_repo = ColdRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None
        self._history_repo = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


class DualStorageUnitOfWork(AbstractUnitOfWork):
    """
    Orchestrates transactions across both Hot and Cold stores.
    Used when syncing data from remote to local.
    """

    def __init__(self, hot_session_factory: Callable[[], AsyncSession], cold_session_factory: Callable[[], AsyncSession]) -> None:
        self._hot_session_factory = hot_session_factory
        self._cold_session_factory = cold_session_factory
        self._hot_session: Optional[AsyncSession] = None
        self._cold_session: Optional[AsyncSession] = None

        self._devices_repo: Optional[HotRepository] = None
        self._history_repo: Optional[ColdRepository] = None

    @property
    def devices(self) -> Optional[HotRepository]:
        return self._devices_repo

    @property
    def history(self) -> Optional[ColdRepository]:
        return self._history_repo

    async def __aenter__(self) -> "DualStorageUnitOfWork":
        self._hot_session = self._hot_session_factory()
        self._cold_session = self._cold_session_factory()

        self._devices_repo = HotRepository(self._hot_session)
        self._history_repo = ColdRepository(self._cold_session)
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
        self._devices_repo = None
        self._history_repo = None

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
