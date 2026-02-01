"""
Infrastructure: Database Connectivity.
Simplified: Single storage engine.
"""

from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from iFactory.infrastructure.configuration.db_settings import DatabaseConfig


@lru_cache(maxsize=1)
def get_storage_engine() -> AsyncEngine:
    """
    Single Storage Engine for all local data.
    Used for history data only (latest status comes from remote).
    """
    config = DatabaseConfig()
    url = config.storage_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


# Legacy compatibility aliases
def get_hot_engine() -> AsyncEngine:
    """Legacy alias - returns storage engine."""
    return get_storage_engine()


def get_cold_engine() -> AsyncEngine:
    """Legacy alias - returns storage engine."""
    return get_storage_engine()


@lru_cache(maxsize=1)
def get_mssql_engine() -> Optional[AsyncEngine]:
    """Async Engine for MSSQL remote source."""
    config = DatabaseConfig()
    url = config.mssql_url

    if not url:
        return None

    if "aioodbc" not in url and "pyodbc" in url:
        url = url.replace("pyodbc", "aioodbc")
    elif "driver=" in url and "aioodbc" not in url:
        if url.startswith("mssql://"):
            url = url.replace("mssql://", "mssql+aioodbc://")

    return create_async_engine(
        url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=30,
        pool_recycle=180,
    )


@lru_cache(maxsize=1)
def get_storage_session_factory() -> async_sessionmaker[AsyncSession]:
    """Factory for storage sessions."""
    engine = get_storage_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Legacy compatibility
def get_hot_session_factory() -> async_sessionmaker[AsyncSession]:
    return get_storage_session_factory()


def get_cold_session_factory() -> async_sessionmaker[AsyncSession]:
    return get_storage_session_factory()
