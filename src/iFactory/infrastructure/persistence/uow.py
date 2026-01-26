"""
SQLAlchemy Unit of Work implementation.
Manages transactional boundaries for repositories.
"""

from __future__ import annotations
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.infrastructure.persistence.repositories.device_repository import SqliteDeviceRepository


class SqliteUnitOfWork(IUnitOfWork):
    """
    SQLAlchemy implementation of the Unit of Work pattern.
    Supports both async context managers (preferred) and sync context manager fallbacks
    to satisfy the IUnitOfWork interface.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self.devices: Optional[SqliteDeviceRepository] = None

    # ==============================================================================
    # Async Context Manager (Preferred for Async SQLAlchemy)
    # ==============================================================================
    async def __aenter__(self):
        self._session = self._session_factory()
        self.devices = SqliteDeviceRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        if self._session:
            await self._session.close()

    # ==============================================================================
    # Sync Context Manager (Required by IUnitOfWork Interface)
    # ==============================================================================
    def __enter__(self):
        """
        Satisfies the IUnitOfWork synchronous contract.
        Note: Consumers should use 'async with' when possible.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    # ==============================================================================
    # Transaction Control
    # ==============================================================================
    async def commit(self):
        """Commit the current transaction."""
        try:
            if self._session:
                await self._session.commit()
        except Exception:
            await self.rollback()
            raise

    async def rollback(self):
        """Rollback the current transaction."""
        if self._session:
            await self._session.rollback()
