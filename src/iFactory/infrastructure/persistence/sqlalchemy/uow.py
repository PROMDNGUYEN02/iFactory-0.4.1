"""
Infrastructure Unit of Work.
Manages transactions for both Hot and Cold repositories.
"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.infrastructure.repositories.sqlalchemy_device_repository import (
    SqlAlchemyDeviceRepository,
)
from iFactory.infrastructure.repositories.sqlalchemy_production_repository import (
    SqlAlchemyProductionRepository,
)


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    Implementation of Unit of Work using SQLAlchemy AsyncSession.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._devices: Optional[SqlAlchemyDeviceRepository] = None
        self._production: Optional[SqlAlchemyProductionRepository] = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self._devices = SqlAlchemyDeviceRepository(self._session)
        self._production = SqlAlchemyProductionRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()
        self._session = None

    async def commit(self) -> None:
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session:
            await self._session.rollback()

    @property
    def devices(self) -> SqlAlchemyDeviceRepository:
        if self._devices is None:
            raise RuntimeError("Unit of Work not started. Use 'async with'.")
        return self._devices

    @property
    def production(self) -> SqlAlchemyProductionRepository:
        if self._production is None:
            raise RuntimeError("Unit of Work not started. Use 'async with'.")
        return self._production
