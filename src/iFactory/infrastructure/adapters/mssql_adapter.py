# src/iFactory/infrastructure/adapters/mssql_adapter.py
"""
MSSQL Adapter - Production-ready with resilience patterns.

Features:
- Query timeout
- Connection timeout
- Retry with exponential backoff
- Circuit breaker pattern
- Proper async operation tracking
- PyInstaller compatible
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Circuit Breaker Implementation
# ============================================================================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing - reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 30.0  # Seconds before trying again
    half_open_max_calls: int = 3  # Test calls in half-open state


@dataclass
class CircuitBreaker:
    """
    Simple circuit breaker for external service protection.

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Service is down, reject requests immediately
    - HALF_OPEN: Testing if service recovered
    """

    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.recovery_timeout:
                    return True
            return False
        return self._half_open_calls < self.config.half_open_max_calls

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.info("[CircuitBreaker] Service recovered, closing circuit")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning("[CircuitBreaker] Failed during recovery, reopening circuit")
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(
                        "[CircuitBreaker] Failure threshold reached (%d), opening circuit",
                        self._failure_count,
                    )
                    self._state = CircuitState.OPEN

    async def try_acquire(self) -> bool:
        """Try to acquire permission for a request."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.recovery_timeout:
                        logger.info("[CircuitBreaker] Recovery timeout passed, entering half-open")
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        return True
                return False

            if self._half_open_calls < self.config.half_open_max_calls:
                return True
            return False

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


# ============================================================================
# Retry Configuration
# ============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (OperationalError, ConnectionError, TimeoutError)


async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    operation_name: str = "operation",
) -> T:
    """Execute function with retry and exponential backoff."""
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt == config.max_attempts:
                logger.error(
                    "[Retry] %s failed after %d attempts: %s",
                    operation_name,
                    attempt,
                    e,
                )
                raise

            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay,
            )
            logger.warning(
                "[Retry] %s attempt %d failed: %s. Retrying in %.1fs...",
                operation_name,
                attempt,
                e,
                delay,
            )
            await asyncio.sleep(delay)

    raise last_exception


# ============================================================================
# MSSQL Adapter
# ============================================================================


@dataclass
class MssqlAdapterConfig:
    """Configuration for MSSQL adapter."""

    query_timeout: float = 30.0
    connect_timeout: int = 10
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


class MssqlAdapter(IRemoteDataSource):
    """
    Adapter for External MSSQL PLC/SCADA Database.

    Features:
    - Query timeout protection
    - Automatic retry with exponential backoff
    - Circuit breaker to prevent cascade failures
    - Graceful shutdown with operation tracking
    - PyInstaller compatible (uses ODBC connection string)
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        config: Optional[MssqlAdapterConfig] = None,
    ) -> None:
        self._config = config or MssqlAdapterConfig()
        self._engine: Optional[AsyncEngine] = None
        self._connection_string = connection_string
        self._is_disposed = False
        self._disposing = False
        self._active_count = 0
        self._lock = asyncio.Lock()

        # Circuit breaker for resilience
        self._circuit_breaker = CircuitBreaker(self._config.circuit_breaker)

        # Create engine if connection string provided
        if connection_string:
            self._create_engine(connection_string)
        else:
            # Try to get from config
            db_config = DatabaseConfig()
            if db_config.mssql_url:
                self._create_engine(db_config.mssql_url)
                logger.info(
                    "[MssqlAdapter] Using config: host=%s, db=%s, driver=%s",
                    db_config.mssql_host,
                    db_config.mssql_db,
                    db_config.mssql_driver,
                )

    def _create_engine(self, url: str) -> None:
        """Create SQLAlchemy async engine."""
        self._engine = create_async_engine(
            url,
            poolclass=NullPool,
            echo=False,
        )
        logger.info(
            "[MssqlAdapter] Engine created with timeout=%ds",
            self._config.query_timeout,
        )

    @property
    def is_available(self) -> bool:
        """Check if adapter is available for requests."""
        return not self._is_disposed and not self._disposing and self._engine is not None and self._circuit_breaker.is_available

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit_breaker.state

    async def _enter_operation(self) -> bool:
        """Enter an operation. Returns False if should abort."""
        async with self._lock:
            if self._disposing or self._is_disposed:
                return False
            if not await self._circuit_breaker.try_acquire():
                logger.warning("[MssqlAdapter] Circuit breaker open, rejecting request")
                return False
            self._active_count += 1
            return True

    async def _exit_operation(self, success: bool = True) -> None:
        """Exit an operation and record result."""
        if success:
            await self._circuit_breaker.record_success()
        else:
            await self._circuit_breaker.record_failure()

        async with self._lock:
            self._active_count = max(0, self._active_count - 1)

    async def _execute_with_timeout(
        self,
        coro,
        timeout: Optional[float] = None,
        operation_name: str = "query",
    ):
        """Execute coroutine with timeout protection."""
        timeout = timeout or self._config.query_timeout
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(
                "[MssqlAdapter] %s timed out after %.1fs",
                operation_name,
                timeout,
            )
            raise TimeoutError(f"{operation_name} timed out after {timeout}s")

    def _parse_datetime(self, val: Any) -> datetime:
        """Parse datetime from various formats."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.now()
        return datetime.now()

    def _map_row(self, row: Any) -> Dict[str, Any]:
        """Map database row to dictionary."""
        equip_code = str(row[0]).strip() if row[0] else "UNKNOWN"
        equip_status = str(row[1]) if row[1] else "0"
        start_time = self._parse_datetime(row[2])
        end_time_val = row[3]
        reason_code = str(row[4]).strip() if row[4] else None
        equip_name = str(row[5]).strip() if row[5] else None
        last_update = self._parse_datetime(end_time_val) if end_time_val else datetime.now()

        return {
            "equip_code": equip_code,
            "equip_status": equip_status,
            "raw_status": equip_status,
            "start_time": start_time,
            "end_time": self._parse_datetime(end_time_val) if end_time_val else None,
            "reason_code": reason_code,
            "equip_name": equip_name,
            "last_update": last_update,
        }

    async def fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch latest status for devices."""
        if not await self._enter_operation():
            return []

        success = False
        try:
            if not self._engine:
                return []

            if equipment_codes is not None and len(equipment_codes) == 0:
                return []

            async def _do_fetch():
                filter_clause = ""
                params: Dict[str, Any] = {}

                if equipment_codes:
                    filter_clause = "AND S.EQUIP_CODE IN :codes"
                    params["codes"] = tuple(equipment_codes)

                query_str = f"""
                WITH RankedStatus AS (
                    SELECT 
                        S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
                        ROW_NUMBER() OVER (PARTITION BY S.EQUIP_CODE ORDER BY S.START_TIME DESC) as rn
                    FROM TT_EQ_STATUS S
                    WHERE (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
                    {filter_clause}
                )
                SELECT 
                    R.EQUIP_CODE, R.EQUIP_STATUS, R.START_TIME, R.END_TIME, R.REASON_CODE,
                    E.EQUIP_NAME
                FROM RankedStatus R
                LEFT JOIN TT_EQ_EQUIPMENT E ON R.EQUIP_CODE = E.EQUIP_CODE
                WHERE R.rn = 1
                """

                if self._disposing:
                    return []

                async with self._engine.connect() as conn:
                    if self._disposing:
                        return []

                    stmt = text(query_str)
                    if equipment_codes:
                        stmt = stmt.bindparams(bindparam("codes", expanding=True))

                    result = await conn.execute(stmt, params)
                    rows = result.fetchall()
                    return [self._map_row(row) for row in rows]

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    operation_name="fetch_latest_status",
                ),
                self._config.retry,
                "fetch_latest_status",
            )
            success = True
            return result

        except (TimeoutError, OperationalError, ConnectionError) as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Bulk fetch error: {e}")
            return []
        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Unexpected error in bulk fetch: {e}")
            return []
        finally:
            await self._exit_operation(success)

    async def fetch_device_status(
        self,
        equip_code: str,
        days: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch device status history for N days."""
        if not self.is_available:
            return []
        now = datetime.now()
        start_of_range = now - timedelta(days=days)
        return await self.fetch_device_history_range(equip_code, start_of_range, now)

    async def fetch_device_history_range(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch device history for a specific time range."""
        if not await self._enter_operation():
            return []

        success = False
        try:
            if not self._engine or self._disposing:
                return []

            async def _do_fetch():
                query = """
                SELECT 
                    S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
                    E.EQUIP_NAME
                FROM TT_EQ_STATUS S
                LEFT JOIN TT_EQ_EQUIPMENT E ON S.EQUIP_CODE = E.EQUIP_CODE
                WHERE S.EQUIP_CODE = :code 
                    AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
                    AND S.START_TIME <= :end_time
                    AND (S.END_TIME >= :start_time OR S.END_TIME IS NULL)
                ORDER BY S.START_TIME ASC
                """

                async with self._engine.connect() as conn:
                    if self._disposing:
                        return []
                    result = await conn.execute(
                        text(query),
                        {
                            "code": equip_code,
                            "start_time": start_time,
                            "end_time": end_time,
                        },
                    )
                    rows = result.fetchall()
                    return [self._map_row(row) for row in rows]

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    operation_name=f"fetch_history({equip_code})",
                ),
                self._config.retry,
                f"fetch_history({equip_code})",
            )
            success = True
            return result

        except (TimeoutError, OperationalError, ConnectionError) as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] History fetch error for {equip_code}: {e}")
            return []
        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Unexpected error in history fetch: {e}")
            return []
        finally:
            await self._exit_operation(success)

    async def fetch_latest_history_records(
        self,
        equip_code: str,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch N most recent history records for a device."""
        if not await self._enter_operation():
            return []

        success = False
        try:
            if not self._engine or self._disposing:
                return []

            async def _do_fetch():
                query = """
                SELECT TOP(:limit)
                    S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
                    E.EQUIP_NAME
                FROM TT_EQ_STATUS S
                LEFT JOIN TT_EQ_EQUIPMENT E ON S.EQUIP_CODE = E.EQUIP_CODE
                WHERE S.EQUIP_CODE = :code 
                    AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
                ORDER BY S.START_TIME DESC
                """

                async with self._engine.connect() as conn:
                    if self._disposing:
                        return []
                    result = await conn.execute(
                        text(query),
                        {"code": equip_code, "limit": limit},
                    )
                    rows = result.fetchall()
                    return [self._map_row(row) for row in rows]

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    operation_name=f"fetch_latest({equip_code})",
                ),
                self._config.retry,
                f"fetch_latest({equip_code})",
            )
            success = True
            return result

        except (TimeoutError, OperationalError, ConnectionError) as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Latest history error for {equip_code}: {e}")
            return []
        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Unexpected error in latest fetch: {e}")
            return []
        finally:
            await self._exit_operation(success)

    async def health_check(self) -> bool:
        """Check if database connection is healthy."""
        if not self._engine or self._is_disposed:
            return False

        try:
            async with self._engine.connect() as conn:
                await asyncio.wait_for(
                    conn.execute(text("SELECT 1")),
                    timeout=5.0,
                )
                return True
        except Exception as e:
            logger.debug("[MssqlAdapter] Health check failed: %s", e)
            return False

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker."""
        self._circuit_breaker.reset()
        logger.info("[MssqlAdapter] Circuit breaker reset manually")

    async def dispose(self) -> None:
        """Dispose with proper waiting for active operations."""
        if self._is_disposed:
            return

        logger.info("[MssqlAdapter] Starting disposal...")

        async with self._lock:
            self._disposing = True
            active = self._active_count

        if active > 0:
            logger.info(f"[MssqlAdapter] Waiting for {active} operations...")
            wait_time = 0
            max_wait = 5.0
            while wait_time < max_wait:
                await asyncio.sleep(0.1)
                wait_time += 0.1
                async with self._lock:
                    if self._active_count == 0:
                        break

            if self._active_count > 0:
                logger.warning(
                    "[MssqlAdapter] Disposing with %d active operations after %.1fs timeout",
                    self._active_count,
                    max_wait,
                )

        self._is_disposed = True
        if self._engine:
            try:
                await self._engine.dispose()
                logger.info("[MssqlAdapter] Engine disposed")
            except Exception as e:
                logger.debug(f"[MssqlAdapter] Engine dispose error: {e}")
            finally:
                self._engine = None


__all__ = [
    "MssqlAdapter",
    "MssqlAdapterConfig",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "RetryConfig",
]
