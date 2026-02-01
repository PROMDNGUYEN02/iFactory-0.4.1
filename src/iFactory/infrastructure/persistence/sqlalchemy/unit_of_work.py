"""
Infrastructure: Unit of Work.
Simplified: Single storage UoW.
"""

from __future__ import annotations

from typing import Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.infrastructure.persistence.sqlalchemy.repositories.device_repository import (
    SqlAlchemyDeviceRepository,
)
from iFactory.infrastructure.persistence.sqlalchemy.repositories.production_repository import (
    SqlAlchemyProductionRepository,
)


class StorageUnitOfWork(AbstractUnitOfWork):
    """
    Single storage unit of work.
    Manages both device cache and history in one transaction.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._devices_repo: Optional[SqlAlchemyDeviceRepository] = None
        self._history_repo: Optional[SqlAlchemyProductionRepository] = None

    @property
    def devices(self) -> Optional[SqlAlchemyDeviceRepository]:
        return self._devices_repo

    @property
    def history(self) -> Optional[SqlAlchemyProductionRepository]:
        return self._history_repo

    async def __aenter__(self) -> "StorageUnitOfWork":
        self._session = self._session_factory()
        self._devices_repo = SqlAlchemyDeviceRepository(self._session)
        self._history_repo = SqlAlchemyProductionRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None
        self._devices_repo = None
        self._history_repo = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()


# Legacy compatibility aliases
HotStorageUnitOfWork = StorageUnitOfWork
ColdStorageUnitOfWork = StorageUnitOfWork
DualStorageUnitOfWork = StorageUnitOfWork
SqlAlchemyUnitOfWork = StorageUnitOfWork
