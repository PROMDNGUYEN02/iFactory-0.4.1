from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from iFactory.infrastructure.config.db_config import DatabaseConfig
from .models import HotBase, ColdBase


class Database:
    """
    Manages the SQLAlchemy Async Engine and Session Factory.
    """

    def __init__(self, config: DatabaseConfig):
        self._engine = create_async_engine(
            config.connection_string,
            echo=config.echo,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def create_tables(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(HotBase.metadata.create_all)
            await conn.run_sync(ColdBase.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()
