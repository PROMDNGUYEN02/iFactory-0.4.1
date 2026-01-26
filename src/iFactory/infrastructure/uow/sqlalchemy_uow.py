from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.infrastructure.persistence.repositories.device_repository_impl import SqliteDeviceRepository
from iFactory.application.exceptions import ApplicationException


class SqliteUnitOfWork(IUnitOfWork):
    def __init__(self, engine: AsyncSQLiteEngine):
        self._engine = engine
        self._session = None
        self.devices: Optional[SqliteDeviceRepository] = None

    async def __aenter__(self):
        self._session = await self._engine.session().__aenter__()
        self.devices = SqliteDeviceRepository(self._engine)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        if self._session:
            await self._session.close()

    async def commit(self):
        try:
            if self._session:
                await self._session.commit()
        except Exception as e:
            await self.rollback()
            raise PersistenceError("Database transaction commit failed", e)

    async def rollback(self):
        if self._session:
            await self._session.rollback()
