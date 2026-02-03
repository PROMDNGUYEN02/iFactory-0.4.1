# src/iFactory/infrastructure/persistence/sqlalchemy/database.py
"""
Infrastructure: Database Connectivity.

Features:
- DatabaseManager class for DI
- Health check support
- Proper async initialization
- PyInstaller compatible
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Optional

from sqlalchemy import text
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


# ============================================================================
# Health Check Support
# ============================================================================


class DatabaseHealth(Enum):
    """Database health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a database health check."""

    status: DatabaseHealth
    latency_ms: float = 0.0
    message: str = ""
    checked_at: datetime = field(default_factory=datetime.now)

    @property
    def is_healthy(self) -> bool:
        return self.status == DatabaseHealth.HEALTHY


# ============================================================================
# DatabaseManager Class
# ============================================================================


class DatabaseManager:
    """
    Database Manager for SQLAlchemy async sessions.

    Features:
    - Async initialization
    - Health check support
    - Proper resource cleanup
    - PyInstaller compatible

    Usage:
        manager = DatabaseManager(db_url)
        await manager.initialize()

        session = manager.session_factory()
        async with session:
            # Use session
            pass

        await manager.dispose()
    """

    __slots__ = (
        "_db_url",
        "_engine",
        "_session_factory",
        "_initialized",
        "_last_health_check",
    )

    def __init__(self, db_url: Optional[str] = None) -> None:
        """
        Initialize DatabaseManager.

        Args:
            db_url: SQLite database URL. If None, uses default storage path.
        """
        self._db_url = db_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._initialized = False
        self._last_health_check: Optional[HealthCheckResult] = None

    async def initialize(self) -> None:
        """Initialize the database engine and create tables."""
        if self._initialized:
            return

        # Ensure directories exist
        PATHS.ensure_directories()
        PATHS.initialize_config_files()

        # Build URL
        if self._db_url:
            url = self._db_url
        else:
            db_path = PATHS.storage_db_path
            url = f"sqlite+aiosqlite:///{db_path}"

        logger.info(f"[Database] Creating storage engine: {PATHS.storage_db_path}")

        config = _get_db_config()

        # Create engine with optimized settings
        self._engine = create_async_engine(
            url,
            echo=config.echo,
            pool_pre_ping=True,
            # SQLite-specific optimizations
            connect_args={"check_same_thread": False} if "sqlite" in url else {},
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # Create tables
        await self._create_tables()

        self._initialized = True
        logger.info(f"[DatabaseManager] Initialized: {url}")

    async def _create_tables(self) -> None:
        """Create database tables."""
        try:
            from iFactory.infrastructure.persistence.sqlalchemy.models import Base

            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("[DatabaseManager] Tables created successfully")
        except Exception as e:
            logger.error(f"[DatabaseManager] Table creation failed: {e}")
            raise

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

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """
        Perform a health check on the database.

        Args:
            timeout: Maximum time to wait for response

        Returns:
            HealthCheckResult with status and latency
        """
        if not self._engine:
            return HealthCheckResult(
                status=DatabaseHealth.UNKNOWN,
                message="Engine not initialized",
            )

        start = datetime.now()

        try:
            async with asyncio.timeout(timeout):
                async with self._engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            latency = (datetime.now() - start).total_seconds() * 1000

            result = HealthCheckResult(
                status=DatabaseHealth.HEALTHY,
                latency_ms=latency,
                message="OK",
            )

        except asyncio.TimeoutError:
            result = HealthCheckResult(
                status=DatabaseHealth.UNHEALTHY,
                latency_ms=timeout * 1000,
                message=f"Timeout after {timeout}s",
            )

        except Exception as e:
            latency = (datetime.now() - start).total_seconds() * 1000
            result = HealthCheckResult(
                status=DatabaseHealth.UNHEALTHY,
                latency_ms=latency,
                message=str(e),
            )

        self._last_health_check = result
        return result

    @property
    def last_health_check(self) -> Optional[HealthCheckResult]:
        """Get the last health check result."""
        return self._last_health_check

    async def dispose(self) -> None:
        """Dispose of database connections."""
        if self._engine:
            try:
                await self._engine.dispose()
                logger.info("[DatabaseManager] Disposed")
            except Exception as e:
                logger.error(f"[DatabaseManager] Dispose error: {e}")
            finally:
                self._engine = None
                self._session_factory = None
                self._initialized = False


# ============================================================================
# Functional API (backward compatibility)
# ============================================================================


@lru_cache(maxsize=1)
def get_storage_engine() -> AsyncEngine:
    """
    Single Storage Engine for all local data.

    Note: Prefer using DatabaseManager for new code.
    """
    PATHS.ensure_directories()

    db_path = PATHS.storage_db_path
    url = f"sqlite+aiosqlite:///{db_path}"
    config = _get_db_config()

    logger.info(f"[Database] Creating storage engine: {db_path}")

    return create_async_engine(
        url,
        echo=config.echo,
        pool_pre_ping=True,
    )


# Legacy aliases
def get_hot_engine() -> AsyncEngine:
    return get_storage_engine()


def get_cold_engine() -> AsyncEngine:
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


# Legacy aliases
get_hot_session_factory = get_storage_session_factory
get_cold_session_factory = get_storage_session_factory


__all__ = [
    # Class-based API
    "DatabaseManager",
    "DatabaseHealth",
    "HealthCheckResult",
    # Functional API
    "get_storage_engine",
    "get_hot_engine",
    "get_cold_engine",
    "get_mssql_engine",
    "get_storage_session_factory",
    "get_hot_session_factory",
    "get_cold_session_factory",
]
