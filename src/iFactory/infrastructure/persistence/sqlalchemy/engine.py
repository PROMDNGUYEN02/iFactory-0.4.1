"""
SQLAlchemy Async Engine Configuration.
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from iFactory.infrastructure.persistence.sqlalchemy.models import Base

logger = logging.getLogger(__name__)


class AsyncDatabaseEngine:
    """Manages Async SQLAlchemy connection pool and session factory."""

    def __init__(self, db_url: str):
        self._engine = create_async_engine(db_url, echo=False)
        self._session_factory = async_sessionmaker(bind=self._engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def dispose(self) -> None:
        await self._engine.dispose()
