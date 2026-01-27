"""
Infrastructure: Async SQLAlchemy Engine Configuration.
Separate engines for Hot Storage (latest) and Cold Storage (history).
"""

from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from iFactory.infrastructure.config.db_config import DatabaseConfig


@lru_cache(maxsize=1)
def get_hot_engine() -> AsyncEngine:
    """
    Hot Storage Engine - For latest status and latest inputs.
    Fast reads/writes for current state.
    """
    config = DatabaseConfig()
    url = config.hot_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_cold_engine() -> AsyncEngine:
    """
    Cold Storage Engine - For history data.
    Status periods history and material input history.
    Supports 24h, 7d, 30d, 60d retention.
    """
    config = DatabaseConfig()
    url = config.cold_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_hot_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory for Hot Storage."""
    engine = get_hot_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@lru_cache(maxsize=1)
def get_cold_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory for Cold Storage."""
    engine = get_cold_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@lru_cache(maxsize=1)
def get_mssql_engine() -> Optional[AsyncEngine]:
    """Async Engine for MSSQL remote source."""
    config = DatabaseConfig()
    url = config.mssql_url

    if not url:
        return None

    async_url = url.replace("pyodbc", "aioodbc")
    return create_async_engine(
        async_url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=30,
        pool_recycle=180,
    )


__all__ = [
    "get_hot_engine",
    "get_cold_engine",
    "get_hot_session_factory",
    "get_cold_session_factory",
    "get_mssql_engine",
]
