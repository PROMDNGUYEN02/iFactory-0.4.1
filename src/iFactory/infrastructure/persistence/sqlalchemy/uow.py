"""
Infrastructure: Async Unit of Work.
Manages async database transactions with SQLAlchemy.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from .repository import SqlAlchemyDeviceRepository


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    Concrete Unit of Work implementation using SQLAlchemy async sessions.
    Manages transaction boundaries and repository instantiation.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self.devices: Optional[SqlAlchemyDeviceRepository] = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.devices = SqlAlchemyDeviceRepository(self._session)
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
