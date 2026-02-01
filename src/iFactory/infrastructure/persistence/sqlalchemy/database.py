# File: infrastructure/persistence/sqlalchemy/database.py
"""
Infrastructure: Database Connectivity.
Simplified: Single storage engine with DatabaseManager class.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from iFactory.infrastructure.configuration.db_settings import DatabaseConfig

logger = logging.getLogger(__name__)


# =============================================================================
# DatabaseManager Class (for DI Container)
# =============================================================================


class DatabaseManager:
    """
    Database Manager for SQLAlchemy async sessions.

    Provides a class-based interface for dependency injection,
    wrapping the functional engine/session factories.
    """

    __slots__ = (
        "_db_url",
        "_engine",
        "_session_factory",
        "_initialized",
    )

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize DatabaseManager.

        Args:
            db_url: SQLite database URL. If None, uses default from config.
        """
        self._db_url = db_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database engine and create tables."""
        if self._initialized:
            return

        config = DatabaseConfig()

        # Determine URL
        if self._db_url:
            url = self._db_url
        else:
            url = config.storage_db_url

        # Convert to async driver if needed
        if "sqlite:///" in url and "aiosqlite" not in url:
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///")

        # Create engine
        self._engine = create_async_engine(
            url,
            echo=config.echo,
            pool_pre_ping=True,
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables
        try:
            from iFactory.infrastructure.persistence.sqlalchemy.models import Base

            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info(f"[DatabaseManager] Initialized: {url}")
        except Exception as e:
            logger.error(f"[DatabaseManager] Table creation failed: {e}")
            raise

        self._initialized = True

    @property
    def engine(self) -> AsyncEngine:
        """Get the async engine."""
        if not self._engine:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory."""
        if not self._session_factory:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        return self._session_factory

    async def dispose(self) -> None:
        """Dispose of database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            logger.info("[DatabaseManager] Disposed")


# =============================================================================
# Functional API (kept for backward compatibility)
# =============================================================================


@lru_cache(maxsize=1)
def get_storage_engine() -> AsyncEngine:
    """
    Single Storage Engine for all local data.
    Used for history data only (latest status comes from remote).
    """
    config = DatabaseConfig()
    url = config.storage_db_url

    if "sqlite:///" in url and "aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///")

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


__all__ = [
    # Class-based API
    "DatabaseManager",
    # Functional API
    "get_storage_engine",
    "get_hot_engine",
    "get_cold_engine",
    "get_mssql_engine",
    "get_storage_session_factory",
    "get_hot_session_factory",
    "get_cold_session_factory",
]
