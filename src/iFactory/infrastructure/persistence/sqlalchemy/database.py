# src/iFactory/infrastructure/persistence/sqlalchemy/database.py
"""
Infrastructure: Database Connectivity.
Simplified: Single storage engine with DatabaseManager class.
Supports PyInstaller frozen environments.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


def _get_db_config():
    """Lazy import to avoid circular dependency."""
    from iFactory.infrastructure.configuration.db_settings import DatabaseConfig

    return DatabaseConfig()


# =============================================================================
# DatabaseManager Class (for DI Container)
# =============================================================================


class DatabaseManager:
    """
    Database Manager for SQLAlchemy async sessions.
    Supports PyInstaller frozen environments.
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
            db_url: SQLite database URL. If None, uses PATHS.storage_db_path.
        """
        self._db_url = db_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database engine and create tables."""
        if self._initialized:
            return

        # Ensure directories exist (important for PyInstaller)
        PATHS.ensure_directories()
        PATHS.initialize_config_files()

        # Build URL from PATHS directly (not from config)
        if self._db_url:
            url = self._db_url
        else:
            # Use PATHS directly to avoid config path issues
            db_path = PATHS.storage_db_path
            url = f"sqlite+aiosqlite:///{db_path}"

        logger.info(f"[DatabaseManager] PATHS.storage_db_path = {PATHS.storage_db_path}")
        logger.info(f"[DatabaseManager] Initializing SQLite: {url}")

        config = _get_db_config()

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

            logger.info("[DatabaseManager] Tables created successfully")
        except Exception as e:
            logger.error(f"[DatabaseManager] Table creation failed: {e}")
            raise

        self._initialized = True
        logger.info(f"[DatabaseManager] Initialized: {url}")

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
    Uses PATHS directly for path resolution.
    """
    # Ensure directories exist
    PATHS.ensure_directories()

    # Build URL from PATHS directly
    db_path = PATHS.storage_db_path
    url = f"sqlite+aiosqlite:///{db_path}"

    config = _get_db_config()

    logger.info(f"[Database] Creating storage engine: {db_path}")

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
    config = _get_db_config()
    url = config.mssql_url

    if not url:
        logger.warning("[Database] MSSQL not configured")
        return None

    logger.info(
        "[Database] Creating MSSQL engine: host=%s, db=%s",
        config.mssql_host,
        config.mssql_db,
    )

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
