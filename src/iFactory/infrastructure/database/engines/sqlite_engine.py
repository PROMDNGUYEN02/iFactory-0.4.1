"""
Async SQLite engine with WAL support and optimized pragmas.

Uses centralized path configuration from iFactory.shared.utils.paths.
"""

from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Type
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from ..base import BaseModel
from ..config import DBConfig, HealthStatus
from .base_engine import DatabaseEngine

__all__ = ["AsyncSQLiteEngine", "SQLiteStoreType"]
logger = logging.getLogger(__name__)


class SQLiteStoreType(str, Enum):
    """SQLite store types."""

    HOT = "hot"
    COLD = "cold"
    CUSTOM = "custom"


class AsyncSQLiteEngine(DatabaseEngine[AsyncSession]):
    """
    Async SQLite engine with WAL mode and connection pooling.

    Features:
        - WAL (Write-Ahead Logging) for better concurrency
        - Optimized pragmas for performance
        - Automatic table creation
        - Health monitoring
        - Periodic checkpointing
        - Centralized path configuration

    Usage:
        # Using store type (recommended)
        engine = AsyncSQLiteEngine.for_hot_store(HotBase)
        engine = AsyncSQLiteEngine.for_cold_store(ColdBase)

        # Using custom path
        engine = AsyncSQLiteEngine(
            db_file=Path("/custom/path/my.db"),
            base_class=MyBase,
        )
    """

    DEFAULT_PRAGMAS: dict[str, Any] = {
        "journal_mode": "WAL",
        "synchronous": "NORMAL",
        "temp_store": "MEMORY",
        "foreign_keys": "ON",
        "busy_timeout": 5000,
    }
    __slots__ = (
        "_name",
        "_db_file",
        "_store_type",
        "_base_class",
        "_config",
        "_engine",
        "_sync_engine",
        "_session_factory",
        "_connected",
        "_pragmas",
    )

    def __init__(
        self,
        db_path_resolver: Optional[Callable[[SQLiteStoreType], Path]] = None,
        db_file: Optional[Path | str] = None,
        base_class: Optional[Type[BaseModel]] = None,
        config: Optional[DBConfig] = None,
        name: Optional[str] = None,
        store_type: SQLiteStoreType = SQLiteStoreType.CUSTOM,
        extra_pragmas: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize SQLite engine.

        Args:
            db_file: Path to database file (optional if store_type is HOT/COLD)
            base_class: SQLAlchemy base class (HotBase or ColdBase)
            config: Database configuration
            name: Engine name for logging
            store_type: Store type (HOT, COLD, or CUSTOM)
            extra_pragmas: Additional pragmas to set
        """
        self._path_resolver = db_path_resolver or self._default_path_resolver
        self._store_type = store_type
        self._config = config or DBConfig()
        self._db_file = self._resolve_db_path(db_file, store_type)
        if name:
            self._name = name
        elif store_type == SQLiteStoreType.HOT:
            self._name = "HotStore"
        elif store_type == SQLiteStoreType.COLD:
            self._name = "ColdStore"
        else:
            self._name = "SQLite"
        self._base_class = base_class
        self._pragmas = {
            **self.DEFAULT_PRAGMAS,
            "cache_size": self._config.cache_size,
            "wal_autocheckpoint": self._config.wal_autocheckpoint,
            "busy_timeout": self._config.busy_timeout,
            **(extra_pragmas or {}),
        }
        self._engine: Optional[AsyncEngine] = None
        self._sync_engine: Optional[Engine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._connected = False
        self._db_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _default_path_resolver(store_type: SQLiteStoreType) -> Path:
        """Default path resolution with fallback."""
        try:
            from iFactory.shared.utils.paths import PATHS

            if store_type == SQLiteStoreType.HOT:
                return PATHS.hot_store_path
            return PATHS.cold_store_path
        except ImportError:
            # Fallback logic here
            pass

    @staticmethod
    def _resolve_db_path(
        db_file: Optional[Path | str], store_type: SQLiteStoreType
    ) -> Path:
        """
        Resolve database file path.

        Uses centralized PATHS configuration for HOT/COLD stores.

        Args:
            db_file: Custom path (optional)
            store_type: Store type

        Returns:
            Resolved Path object
        """
        if db_file is not None:
            return Path(db_file)
        try:
            from iFactory.shared.utils.paths import PATHS

            if store_type == SQLiteStoreType.HOT:
                return PATHS.hot_store_path
            elif store_type == SQLiteStoreType.COLD:
                return PATHS.cold_store_path
            else:
                raise ValueError("db_file is required when store_type is CUSTOM")
        except ImportError:
            logger.warning("PATHS module not found, using fallback paths")
            from pathlib import Path as FallbackPath

            current = FallbackPath(__file__).resolve()
            for parent in current.parents:
                data_dir = parent / "data"
                if data_dir.exists():
                    if store_type == SQLiteStoreType.HOT:
                        return data_dir / "hot_store.db"
                    elif store_type == SQLiteStoreType.COLD:
                        return data_dir / "cold_store.db"
            raise ValueError("Cannot determine database path")

    @classmethod
    def for_hot_store(
        cls,
        base_class: Type[BaseModel],
        config: Optional[DBConfig] = None,
        extra_pragmas: Optional[dict[str, Any]] = None,
    ) -> "AsyncSQLiteEngine":
        """
        Create engine for hot store (real-time data).

        Uses centralized PATHS configuration.

        Args:
            base_class: SQLAlchemy HotBase class
            config: Optional database configuration
            extra_pragmas: Additional pragmas

        Returns:
            Configured AsyncSQLiteEngine
        """
        return cls(
            base_class=base_class,
            config=config,
            store_type=SQLiteStoreType.HOT,
            extra_pragmas=extra_pragmas,
        )

    @classmethod
    def for_cold_store(
        cls,
        base_class: Type[BaseModel],
        config: Optional[DBConfig] = None,
        extra_pragmas: Optional[dict[str, Any]] = None,
    ) -> "AsyncSQLiteEngine":
        """
        Create engine for cold store (historical data).

        Uses centralized PATHS configuration.

        Args:
            base_class: SQLAlchemy ColdBase class
            config: Optional database configuration
            extra_pragmas: Additional pragmas

        Returns:
            Configured AsyncSQLiteEngine
        """
        return cls(
            base_class=base_class,
            config=config,
            store_type=SQLiteStoreType.COLD,
            extra_pragmas=extra_pragmas,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def db_file(self) -> Path:
        return self._db_file

    @property
    def store_type(self) -> SQLiteStoreType:
        return self._store_type

    @property
    def engine(self) -> AsyncEngine:
        """Get async engine (raises if not connected)."""
        if self._engine is None:
            raise RuntimeError(f"{self._name} not connected")
        return self._engine

    async def connect(self) -> None:
        """Initialize SQLite connection with optimized settings."""
        if self._connected:
            return
        if self._base_class is None:
            raise RuntimeError(f"{self._name}: base_class is required")
        logger.debug(f"[{self._name}] Connecting to: {self._db_file}")
        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{self._db_file}",
            echo=self._config.echo,
            future=True,
            connect_args={"timeout": self._config.connect_timeout},
            pool_pre_ping=True,
        )
        self._sync_engine = create_engine(
            f"sqlite:///{self._db_file}", echo=self._config.echo, future=True
        )
        self._register_pragma_listener()
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(self._base_class.metadata.create_all)
        self._connected = True
        logger.info(f"[{self._name}] Connected: {self._db_file.name}")

    def _register_pragma_listener(self) -> None:
        """Register SQLite PRAGMA settings on each connection."""
        pragmas = self._pragmas

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            for pragma_name, pragma_value in pragmas.items():
                try:
                    cursor.execute(f"PRAGMA {pragma_name}={pragma_value}")
                except Exception as e:
                    logger.debug(f"PRAGMA {pragma_name} failed: {e}")
            cursor.close()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async session with automatic commit/rollback.

        Yields:
            AsyncSession for database operations
        """
        if self._session_factory is None:
            raise RuntimeError(f"{self._name} not connected")
        async with self._session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    async def health_check(self, timeout: float = 5.0) -> HealthStatus:
        """Check database health with timeout."""
        if not self._connected:
            return HealthStatus.failure(self._name, "Not connected")
        start = time.perf_counter()
        try:
            async with asyncio.timeout(timeout):
                async with self.engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
            latency = (time.perf_counter() - start) * 1000
            return HealthStatus.success(
                self._name,
                latency,
                db_file=str(self._db_file),
                store_type=self._store_type.value,
            )
        except asyncio.TimeoutError:
            return HealthStatus.failure(self._name, f"Timeout after {timeout}s")
        except Exception as e:
            return HealthStatus.failure(self._name, str(e))

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        db_size = self._db_file.stat().st_size if self._db_file.exists() else 0
        wal_file = Path(f"{self._db_file}-wal")
        wal_size = wal_file.stat().st_size if wal_file.exists() else 0
        shm_file = Path(f"{self._db_file}-shm")
        shm_size = shm_file.stat().st_size if shm_file.exists() else 0
        stats = {
            "name": self._name,
            "store_type": self._store_type.value,
            "connected": self._connected,
            "db_file": str(self._db_file),
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "wal_size_bytes": wal_size,
            "wal_size_mb": round(wal_size / 1024 / 1024, 2),
            "shm_size_bytes": shm_size,
        }
        if self._connected:
            try:
                async with self.session() as session:
                    result = await session.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table'")
                    )
                    tables = [row[0] for row in result.fetchall()]
                    stats["tables"] = tables
                    stats["table_count"] = len(tables)
            except Exception:
                pass
        return stats

    async def checkpoint(self, mode: str = "PASSIVE") -> bool:
        """
        Perform WAL checkpoint.

        Args:
            mode: Checkpoint mode (PASSIVE, FULL, RESTART, TRUNCATE)

        Returns:
            True if successful
        """
        if not self._connected:
            return False
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text(f"PRAGMA wal_checkpoint({mode})"))
            logger.debug(f"[{self._name}] Checkpoint ({mode}) completed")
            return True
        except Exception as e:
            logger.warning(f"[{self._name}] Checkpoint failed: {e}")
            return False

    async def vacuum(self) -> bool:
        """
        Vacuum database to reclaim space.

        Note: This can be slow for large databases.
        """
        if not self._connected:
            return False
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("VACUUM"))
            logger.info(f"[{self._name}] VACUUM completed")
            return True
        except Exception as e:
            logger.warning(f"[{self._name}] VACUUM failed: {e}")
            return False

    async def optimize(self) -> bool:
        """
        Optimize database (analyze + reindex).

        Returns:
            True if successful
        """
        if not self._connected:
            return False
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("ANALYZE"))
                await conn.execute(text("REINDEX"))
            logger.info(f"[{self._name}] Optimization completed")
            return True
        except Exception as e:
            logger.warning(f"[{self._name}] Optimization failed: {e}")
            return False

    async def execute_raw(self, sql: str, params: Optional[dict] = None) -> Any:
        """
        Execute raw SQL query.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            Query result
        """
        async with self.session() as session:
            result = await session.execute(text(sql), params or {})
            return result

    async def disconnect(self) -> None:
        """Clean up with final checkpoint."""
        if not self._connected:
            return
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        except Exception as e:
            logger.debug(f"[{self._name}] Final checkpoint failed: {e}")
        if self._engine:
            await self._engine.dispose()
        if self._sync_engine:
            self._sync_engine.dispose()
        self._engine = None
        self._sync_engine = None
        self._session_factory = None
        self._connected = False
        logger.info(f"[{self._name}] Disconnected")

    def __repr__(self) -> str:
        return f"AsyncSQLiteEngine(name={self._name!r}, store_type={self._store_type.value}, connected={self._connected}, db_file={self._db_file.name!r})"
