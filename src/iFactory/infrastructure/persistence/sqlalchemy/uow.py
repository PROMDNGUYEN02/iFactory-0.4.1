"""
Infrastructure: Async Unit of Work.
Quản lý Transaction bất đồng bộ.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork

# [FIXED] Import class implementation cụ thể, KHÔNG import Abstract Class
from iFactory.infrastructure.persistence.sqlalchemy.repository import SqlAlchemyDeviceRepository


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._session: AsyncSession = None

    async def __aenter__(self):
        self._session = self._session_factory()
        # [FIXED] Khởi tạo SqlAlchemyDeviceRepository (Concrete Class)
        self.devices = SqlAlchemyDeviceRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        if self._session:
            await self._session.close()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
