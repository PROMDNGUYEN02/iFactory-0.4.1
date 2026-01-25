from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.application.interfaces.unit_of_work import IUnitOfWork
from src.infrastructure.repositories.sqlalchemy_device_repository import SQLAlchemyDeviceRepository
from src.application.exceptions import ApplicationException


class SQLAlchemyUnitOfWork(IUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession = None
        self.devices: SQLAlchemyDeviceRepository = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.devices = SQLAlchemyDeviceRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        try:
            await self._session.commit()
        except Exception as e:
            await self.rollback()
            raise ApplicationException(f"Failed to commit transaction: {str(e)}")

    async def rollback(self) -> None:
        await self._session.rollback()
