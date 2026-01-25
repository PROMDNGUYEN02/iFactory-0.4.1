from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.infrastructure.config.database_config import DatabaseConfig


class DatabaseManager:
    def __init__(self, config: DatabaseConfig):
        self._engine = create_async_engine(
            config.connection_string,
            echo=config.echo,
            pool_size=config.pool_size if "sqlite" not in config.connection_string else None,
            max_overflow=config.max_overflow if "sqlite" not in config.connection_string else None,
        )
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False, class_=AsyncSession)

    async def init_db(self, base):
        async with self._engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory
