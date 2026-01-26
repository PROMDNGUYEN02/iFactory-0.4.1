"""
SQLAlchemy Unit of Work.
Coordinates transactional boundaries. Database Agnostic.
"""

from __future__ import annotations
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.infrastructure.persistence.sqlalchemy.repository import SqlAlchemyDeviceRepository


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """
    Implementation of the IUnitOfWork pattern using SQLAlchemy.
    Binds Application interface contracts to Infrastructure implementations.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self.devices: Optional[DeviceRepository] = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.devices = SqlAlchemyDeviceRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        if self._session:
            await self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def commit(self):
        if self._session:
            await self._session.commit()

    async def rollback(self):
        if self._session:
            await self._session.rollback()
