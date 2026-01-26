"""
Database orchestrator - Coordinates all database connections.

Uses centralized path configuration from iFactory.shared.utils.paths.
"""

from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Any, Optional
from .base import HotBase, ColdBase
from .config import DBConfig, RemoteDBParams, HealthStatus
from .engines.sqlite_engine import AsyncSQLiteEngine, SQLiteStoreType
from .engines.mssql_engine import MSSQLEngine

__all__ = ["DatabaseOrchestrator"]
logger = logging.getLogger(__name__)


def _get_default_data_dir() -> Path:
    """
    Get default data directory from centralized paths.

    Returns:
        Path to data directory
    """
    try:
        from iFactory.shared.utils.paths import PATHS

        return PATHS.data_dir
    except ImportError:
        logger.warning("PATHS module not found, using fallback")
        current = Path(__file__).resolve()
        for parent in current.parents:
            data_dir = parent / "data"
            if data_dir.exists():
                return data_dir
        fallback = current.parent.parent.parent.parent / "data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class DatabaseOrchestrator:
    """
    Orchestrates all database connections.

    Manages:
        - Hot store (SQLite) - Latest device state
        - Cold store (SQLite) - Historical data
        - Remote store (MSSQL) - Source data

    Database paths are resolved from centralized PATHS configuration.

    Usage:
        # Using default paths (recommended)
        orchestrator = DatabaseOrchestrator(remote=remote_params)
        await orchestrator.initialize()

        # Using custom base directory
        orchestrator = DatabaseOrchestrator(
            base_dir=Path("/custom/path"),
            remote=remote_params,
        )

        # As context manager
        async with DatabaseOrchestrator(remote=remote_params) as db:
            async with db.hot.session() as session:
                # ... database operations
    """

    __slots__ = (
        "_config",
        "_data_dir",
        "_hot",
        "_cold",
        "_mssql",
        "_disposed",
        "_use_centralized_paths",
    )

    def __init__(
        self,
        base_dir: Optional[Path | str] = None,
        remote: Optional[RemoteDBParams] = None,
        config: Optional[DBConfig] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            base_dir: Base directory for data files (optional - uses PATHS if None)
            remote: MSSQL connection parameters
            config: Database configuration
        """
        self._config = config or DBConfig()
        self._disposed = False
        self._use_centralized_paths = base_dir is None
        if base_dir is not None:
            self._data_dir = Path(base_dir)
            if not self._data_dir.name == "data":
                self._data_dir = self._data_dir / "data"
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._hot = AsyncSQLiteEngine(
                db_file=self._data_dir / "hot_store.db",
                base_class=HotBase,
                config=self._config,
                name="HotStore",
                store_type=SQLiteStoreType.CUSTOM,
            )
            self._cold = AsyncSQLiteEngine(
                db_file=self._data_dir / "cold_store.db",
                base_class=ColdBase,
                config=self._config,
                name="ColdStore",
                store_type=SQLiteStoreType.CUSTOM,
            )
        else:
            self._data_dir = _get_default_data_dir()
            self._hot = AsyncSQLiteEngine.for_hot_store(base_class=HotBase, config=self._config)
            self._cold = AsyncSQLiteEngine.for_cold_store(base_class=ColdBase, config=self._config)
        self._mssql = MSSQLEngine(remote=remote or RemoteDBParams(), config=self._config, name="RemoteDB")
        logger.debug(f"DatabaseOrchestrator created: data_dir={self._data_dir}, centralized_paths={self._use_centralized_paths}")

    @classmethod
    def with_defaults(cls, remote: Optional[RemoteDBParams] = None, config: Optional[DBConfig] = None) -> "DatabaseOrchestrator":
        """
        Create orchestrator with default paths from PATHS.

        This is the recommended way to create an orchestrator.

        Args:
            remote: MSSQL connection parameters
            config: Database configuration

        Returns:
            Configured DatabaseOrchestrator
        """
        return cls(base_dir=None, remote=remote, config=config)

    @classmethod
    def with_custom_dir(
        cls,
        data_dir: Path | str,
        remote: Optional[RemoteDBParams] = None,
        config: Optional[DBConfig] = None,
    ) -> "DatabaseOrchestrator":
        """
        Create orchestrator with custom data directory.

        Args:
            data_dir: Custom data directory path
            remote: MSSQL connection parameters
            config: Database configuration

        Returns:
            Configured DatabaseOrchestrator
        """
        return cls(base_dir=data_dir, remote=remote, config=config)

    @property
    def hot(self) -> AsyncSQLiteEngine:
        """Get hot store engine."""
        return self._hot

    @property
    def cold(self) -> AsyncSQLiteEngine:
        """Get cold store engine."""
        return self._cold

    @property
    def mssql(self) -> MSSQLEngine:
        """Get MSSQL engine."""
        return self._mssql

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self._data_dir

    @property
    def is_initialized(self) -> bool:
        """Check if all local stores are connected."""
        return self._hot.is_connected and self._cold.is_connected

    @property
    def is_remote_connected(self) -> bool:
        """Check if remote MSSQL is connected."""
        return self._mssql.is_connected

    @property
    def uses_centralized_paths(self) -> bool:
        """Check if using centralized PATHS configuration."""
        return self._use_centralized_paths

    async def initialize(self) -> dict[str, bool]:
        """
        Initialize all database connections.

        Returns:
            Dictionary with initialization status for each engine
        """
        if self._disposed:
            raise RuntimeError("Orchestrator has been disposed")
        results = await asyncio.gather(
            self._hot.connect(),
            self._cold.connect(),
            self._mssql.connect(),
            return_exceptions=True,
        )
        status = {}
        names = ["hot", "cold", "mssql"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize {name}: {result}")
                status[name] = False
            else:
                status[name] = True
        logger.info(f"DatabaseOrchestrator initialized: hot={status['hot']}, cold={status['cold']}, mssql={status['mssql']}")
        return status

    async def dispose(self) -> None:
        """Dispose all database connections."""
        if self._disposed:
            return
        self._disposed = True
        await asyncio.gather(
            self._hot.disconnect(),
            self._cold.disconnect(),
            self._mssql.disconnect(),
            return_exceptions=True,
        )
        logger.info("DatabaseOrchestrator disposed")

    async def health_check(self, timeout: float = 5.0) -> dict[str, HealthStatus]:
        """
        Check health of all databases.

        Args:
            timeout: Timeout for each health check

        Returns:
            Dictionary mapping engine name to health status
        """
        (hot_health, cold_health, mssql_health) = await asyncio.gather(
            self._hot.health_check(timeout),
            self._cold.health_check(timeout),
            self._mssql.health_check(timeout),
        )
        return {"hot": hot_health, "cold": cold_health, "mssql": mssql_health}

    async def is_healthy(self, timeout: float = 5.0) -> bool:
        """
        Quick health check - returns True if all local DBs are healthy.

        MSSQL health is not required for local operation.
        """
        statuses = await self.health_check(timeout)
        return statuses["hot"].healthy and statuses["cold"].healthy

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics for all databases."""
        (hot_stats, cold_stats, mssql_stats) = await asyncio.gather(self._hot.get_stats(), self._cold.get_stats(), self._mssql.get_stats())
        return {
            "hot": hot_stats,
            "cold": cold_stats,
            "mssql": mssql_stats,
            "data_dir": str(self._data_dir),
            "centralized_paths": self._use_centralized_paths,
            "disposed": self._disposed,
        }

    def get_status(self) -> dict[str, bool]:
        """
        Get quick status of all connections.

        Returns:
            Dictionary with connection status for each engine
        """
        return {
            "hot": self._hot.is_connected,
            "cold": self._cold.is_connected,
            "mssql": self._mssql.is_connected,
        }

    async def checkpoint_all(self, mode: str = "PASSIVE") -> dict[str, bool]:
        """
        Checkpoint all SQLite databases.

        Args:
            mode: Checkpoint mode (PASSIVE, FULL, RESTART, TRUNCATE)

        Returns:
            Dictionary with success status for each store
        """
        (hot_result, cold_result) = await asyncio.gather(self._hot.checkpoint(mode), self._cold.checkpoint(mode))
        return {"hot": hot_result, "cold": cold_result}

    async def vacuum_all(self) -> dict[str, bool]:
        """
        Vacuum all SQLite databases.

        Warning: This can be slow for large databases.
        """
        (hot_result, cold_result) = await asyncio.gather(self._hot.vacuum(), self._cold.vacuum())
        return {"hot": hot_result, "cold": cold_result}

    async def optimize_all(self) -> dict[str, bool]:
        """
        Optimize all SQLite databases (analyze + reindex).

        Returns:
            Dictionary with success status for each store
        """
        results = {}
        if hasattr(self._hot, "optimize"):
            results["hot"] = await self._hot.optimize()
        else:
            results["hot"] = False
        if hasattr(self._cold, "optimize"):
            results["cold"] = await self._cold.optimize()
        else:
            results["cold"] = False
        return results

    async def __aenter__(self) -> "DatabaseOrchestrator":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *_) -> None:
        """Async context manager exit."""
        await self.dispose()

    def __repr__(self) -> str:
        return f"DatabaseOrchestrator(data_dir={self._data_dir}, hot={self._hot.is_connected}, cold={self._cold.is_connected}, mssql={self._mssql.is_connected})"
