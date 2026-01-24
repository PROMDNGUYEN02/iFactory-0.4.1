"""
MSSQL engine with connection pooling and retry logic.
"""

from __future__ import annotations
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from ..config import DBConfig, RemoteDBParams, HealthStatus
from .base_engine import DatabaseEngine

__all__ = ["MSSQLEngine"]
logger = logging.getLogger(__name__)


class MSSQLConnectionError(Exception):
    """MSSQL connection error."""

    pass


class MSSQLEngine(DatabaseEngine[Session]):
    """
    MSSQL engine with connection pooling and retry logic.

    Features:
        - Connection pooling via QueuePool
        - Automatic driver detection (prefers modern, falls back to SQL Server)
        - Retry logic for transient failures
        - Health monitoring

    Note:
        Uses synchronous SQLAlchemy sessions wrapped in asyncio.to_thread
        because pyodbc doesn't support async natively.
    """

    DRIVER_PRIORITY = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
    ]
    DEFAULT_DRIVER = "SQL Server"
    MODERN_DRIVERS = {
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
    }
    __slots__ = (
        "_name",
        "_config",
        "_remote",
        "_engine",
        "_session_factory",
        "_connected",
        "_driver",
    )

    def __init__(
        self,
        remote: RemoteDBParams,
        config: Optional[DBConfig] = None,
        name: str = "MSSQL",
    ):
        """
        Initialize MSSQL engine.

        Args:
            remote: Remote connection parameters
            config: Database configuration
            name: Engine name for logging
        """
        self._name = name
        self._config = config or DBConfig()
        self._remote = remote
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker[Session]] = None
        self._connected = False
        self._driver: Optional[str] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def driver(self) -> Optional[str]:
        """Get detected/configured driver."""
        return self._driver

    def _detect_driver(self) -> str:
        """
        Detect best available ODBC driver.

        Strategy:
            1. If driver specified in config, use it
            2. Try modern drivers in priority order
            3. Fall back to "SQL Server" (always available on Windows)
        """
        if self._remote.driver:
            logger.debug(
                f"[{self._name}] Using configured driver: {self._remote.driver}"
            )
            return self._remote.driver
        try:
            import pyodbc

            available = set(pyodbc.drivers())
            logger.debug(f"[{self._name}] Available ODBC drivers: {sorted(available)}")
            for driver in self.DRIVER_PRIORITY:
                if driver in available:
                    logger.info(f"[{self._name}] Using modern driver: {driver}")
                    return driver
            if self.DEFAULT_DRIVER in available:
                logger.info(
                    f"[{self._name}] Using default driver: {self.DEFAULT_DRIVER}"
                )
                return self.DEFAULT_DRIVER
            if available:
                driver = sorted(available)[0]
                logger.warning(f"[{self._name}] Using fallback driver: {driver}")
                return driver
        except ImportError:
            logger.warning(f"[{self._name}] pyodbc not installed")
        except Exception as e:
            logger.warning(f"[{self._name}] Driver detection failed: {e}")
        logger.info(f"[{self._name}] Defaulting to: {self.DEFAULT_DRIVER}")
        return self.DEFAULT_DRIVER

    def _is_modern_driver(self, driver: str) -> bool:
        """Check if driver supports modern SSL options."""
        return driver in self.MODERN_DRIVERS

    def _build_connection_string(self) -> str:
        """Build ODBC connection string."""
        if self._remote.dsn:
            return f"mssql+pyodbc:///?odbc_connect={quote_plus(self._remote.dsn)}"
        driver = self._detect_driver()
        self._driver = driver
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={self._remote.host}",
            f"DATABASE={self._remote.database}",
        ]
        if self._remote.user:
            parts.extend([f"UID={self._remote.user}", f"PWD={self._remote.password}"])
        else:
            parts.append("Trusted_Connection=yes")
        if self._is_modern_driver(driver):
            parts.extend(
                [
                    f"Encrypt={('yes' if self._remote.encrypt else 'no')}",
                    f"TrustServerCertificate={('yes' if self._remote.trust_cert else 'no')}",
                ]
            )
        else:
            logger.warning(
                f"[{self._name}] Driver '{driver}' is legacy - SSL options skipped "
            )
        parts.append("MARS_Connection=Yes")
        parts.append(f"Connection Timeout={self._config.connect_timeout}")
        odbc_string = ";".join(parts)
        if self._remote.password:
            safe_string = odbc_string.replace(self._remote.password, "***")
        else:
            safe_string = odbc_string
        logger.debug(f"[{self._name}] Connection string: {safe_string}")
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_string)}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, MSSQLConnectionError)),
        reraise=True,
    )
    async def connect(self) -> None:
        """Connect with retry logic."""
        if self._connected:
            return
        if not self._remote.is_configured:
            logger.warning(f"[{self._name}] Not configured, skipping connection")
            return
        try:
            connection_string = self._build_connection_string()
            engine = create_engine(
                connection_string,
                echo=self._config.echo,
                future=True,
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                pool_timeout=self._config.pool_timeout,
                pool_recycle=self._config.pool_recycle,
                pool_pre_ping=True,
                poolclass=QueuePool,
            )
            await asyncio.to_thread(self._test_connection, engine)
            self._engine = engine
            self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            self._connected = True
            logger.info(
                f"[{self._name}] Connected to {self._remote.host}/{self._remote.database} (driver: {self._driver})"
            )
        except Exception as e:
            logger.error(f"[{self._name}] Connection failed: {e}")
            raise MSSQLConnectionError(str(e)) from e

    def _test_connection(self, engine: Engine) -> None:
        """Test connection synchronously."""
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Session, None]:
        """
        Get sync session wrapped for async use.

        Note: Operations within the session are synchronous.
        For CPU-bound queries, consider using run_in_executor.
        """
        if not self._session_factory:
            raise RuntimeError(f"{self._name} not connected")
        sess = self._session_factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    async def execute_async(self, query: str, params: Optional[dict] = None) -> Any:
        """
        Execute query asynchronously using thread pool.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Query result
        """

        def _execute():
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return result.fetchall()

        return await asyncio.to_thread(_execute)

    async def health_check(self, timeout: float = 5.0) -> HealthStatus:
        """Check database health with timeout."""
        if not self._engine:
            if not self._remote.is_configured:
                return HealthStatus.failure(self._name, "Not configured")
            return HealthStatus.failure(self._name, "Not connected")
        start = time.perf_counter()
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._test_connection, self._engine), timeout=timeout
            )
            latency = (time.perf_counter() - start) * 1000
            return HealthStatus.success(
                self._name,
                latency,
                host=self._remote.host,
                database=self._remote.database,
            )
        except asyncio.TimeoutError:
            return HealthStatus.failure(self._name, f"Timeout after {timeout}s")
        except Exception as e:
            return HealthStatus.failure(self._name, str(e))

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        stats = {
            "name": self._name,
            "connected": self._connected,
            "configured": self._remote.is_configured,
            "driver": self._driver,
        }
        if self._connected and self._engine:
            pool = self._engine.pool
            stats.update(
                {
                    "pool_size": pool.size(),
                    "pool_checked_out": pool.checkedout(),
                    "pool_overflow": pool.overflow(),
                    "host": self._remote.host,
                    "database": self._remote.database,
                }
            )
        return stats

    async def disconnect(self) -> None:
        """Dispose connection pool."""
        if not self._connected:
            return
        if self._engine:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None
        self._connected = False
        logger.info(f"[{self._name}] Disconnected")


class MSSQLError(Exception):
    """Base MSSQL error."""

    pass


class MSSQLConnectionError(MSSQLError):
    """Connection failure."""

    pass


class MSSQLTimeoutError(MSSQLError):
    """Query timeout."""

    pass


class MSSQLDriverError(MSSQLError):
    """ODBC driver issue."""

    pass
