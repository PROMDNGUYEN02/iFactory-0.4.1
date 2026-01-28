"""
Infrastructure: Database Connectivity.
Factories for Async SQLAlchemy Engines (Hot, Cold, and MSSQL).
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
def get_hot_engine() -> AsyncEngine:
    """
    Hot Storage Engine.
    Used for latest state (read-heavy, frequent writes).
    """
    config = DatabaseConfig()
    # Ensure asyncio compatible driver
    url = config.hot_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_cold_engine() -> AsyncEngine:
    """
    Cold Storage Engine.
    Used for historical data (write-heavy logs, range queries).
    """
    config = DatabaseConfig()
    url = config.cold_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_mssql_engine() -> Optional[AsyncEngine]:
    """
    Async Engine for MSSQL remote source.
    """
    config = DatabaseConfig()
    url = config.mssql_url

    if not url:
        return None

    # Ensure aioodbc driver is used for async support
    if "aioodbc" not in url and "pyodbc" in url:
        url = url.replace("pyodbc", "aioodbc")
    elif "driver=" in url and "aioodbc" not in url:
        # Fallback if protocol isn't explicit but it is an mssql url
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
def get_hot_session_factory() -> async_sessionmaker[AsyncSession]:
    """Factory for Hot Storage sessions."""
    engine = get_hot_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@lru_cache(maxsize=1)
def get_cold_session_factory() -> async_sessionmaker[AsyncSession]:
    """Factory for Cold Storage sessions."""
    engine = get_cold_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
