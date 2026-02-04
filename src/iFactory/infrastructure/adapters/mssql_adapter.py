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
- Material Input fetching - OPTIMIZED for large tables (362GB+)
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
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class CircuitBreaker:
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
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= self.config.recovery_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        return True
                return False

            if self._half_open_calls < self.config.half_open_max_calls:
                return True
            return False

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


# ============================================================================
# Retry Configuration
# ============================================================================


@dataclass
class RetryConfig:
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
# Material Input Data Class
# ============================================================================


@dataclass
class MaterialInputRecord:
    lot_no: str
    material_batch: str
    material_name: str
    feed_time: datetime
    feed_qty: float = 0.0
    feed_user: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_no": self.lot_no,
            "material_batch": self.material_batch,
            "material_name": self.material_name,
            "feed_time": self.feed_time.isoformat() if self.feed_time else None,
            "feed_qty": self.feed_qty,
            "feed_user": self.feed_user,
        }


# ============================================================================
# MSSQL Adapter
# ============================================================================


@dataclass
class MssqlAdapterConfig:
    query_timeout: float = 30.0
    connect_timeout: int = 10
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)


class MssqlAdapter(IRemoteDataSource):
    """
    Adapter for External MSSQL PLC/SCADA Database.

    Optimized for large tables (362GB+) with proper index usage.
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
        self._circuit_breaker = CircuitBreaker(self._config.circuit_breaker)

        if connection_string:
            self._create_engine(connection_string)
        else:
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
        return not self._is_disposed and not self._disposing and self._engine is not None and self._circuit_breaker.is_available

    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit_breaker.state

    async def _enter_operation(self) -> bool:
        async with self._lock:
            if self._disposing or self._is_disposed:
                return False
            if not await self._circuit_breaker.try_acquire():
                return False
            self._active_count += 1
            return True

    async def _exit_operation(self, success: bool = True) -> None:
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

    # =========================================================================
    # Material Input Fetching - Progressive filter from small to large
    # =========================================================================

    async def fetch_material_inputs(
        self,
        equip_code: str,
    ) -> List[MaterialInputRecord]:
        """
        Fetch material inputs from yntti.dbo.RPT_FEEDING_DETAIL.

        Progressive date filter (small to large for fast machines):
        1 min → 5 min → 30 min → 2 hours → 12 hours → 2 days

        If no data after 2 days, return empty list.
        """
        if self._disposing or self._is_disposed:
            return []

        if not await self._enter_operation():
            return []

        success = False
        try:
            if not self._engine or self._disposing:
                return []

            async def _do_fetch():
                if self._disposing or self._is_disposed:
                    return []

                # Progressive filter: 1min → 5min → 30min → 2h → 12h → 2days
                # Fast machines find LOT in first few attempts
                # Max 2 days - if still null, return empty

                query = """
                DECLARE @latest_lot NVARCHAR(100);
                
                -- 1. Try last 1 minute (for fast machines)
                SELECT TOP 1 @latest_lot = LOT_NO
                FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                WHERE EQUIP_CODE = :equip_code
                  AND FEED_TIME >= DATEADD(MINUTE, -1, GETDATE())
                ORDER BY FEED_TIME DESC;
                
                -- 2. Try last 5 minutes
                IF @latest_lot IS NULL
                BEGIN
                    SELECT TOP 1 @latest_lot = LOT_NO
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE EQUIP_CODE = :equip_code
                      AND FEED_TIME >= DATEADD(MINUTE, -5, GETDATE())
                    ORDER BY FEED_TIME DESC;
                END
                
                -- 3. Try last 30 minutes
                IF @latest_lot IS NULL
                BEGIN
                    SELECT TOP 1 @latest_lot = LOT_NO
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE EQUIP_CODE = :equip_code
                      AND FEED_TIME >= DATEADD(MINUTE, -30, GETDATE())
                    ORDER BY FEED_TIME DESC;
                END
                
                -- 4. Try last 2 hours
                IF @latest_lot IS NULL
                BEGIN
                    SELECT TOP 1 @latest_lot = LOT_NO
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE EQUIP_CODE = :equip_code
                      AND FEED_TIME >= DATEADD(HOUR, -2, GETDATE())
                    ORDER BY FEED_TIME DESC;
                END
                
                -- 5. Try last 12 hours
                IF @latest_lot IS NULL
                BEGIN
                    SELECT TOP 1 @latest_lot = LOT_NO
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE EQUIP_CODE = :equip_code
                      AND FEED_TIME >= DATEADD(HOUR, -12, GETDATE())
                    ORDER BY FEED_TIME DESC;
                END
                
                -- 6. Try last 2 days (maximum)
                IF @latest_lot IS NULL
                BEGIN
                    SELECT TOP 1 @latest_lot = LOT_NO
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE EQUIP_CODE = :equip_code
                      AND FEED_TIME >= DATEADD(DAY, -2, GETDATE())
                    ORDER BY FEED_TIME DESC;
                END
                
                -- If still NULL after 2 days, return nothing (no more fallback)
                -- Get materials for the LOT (uses LOT_NO index - very fast)
                IF @latest_lot IS NOT NULL
                BEGIN
                    SELECT 
                        LOT_NO,
                        MATERIAL_BATCH,
                        MATERIAL_NAME,
                        MIN(FEED_TIME) as FEED_TIME,
                        MAX(FEED_QTY) as FEED_QTY,
                        MAX(ISNULL(FEED_USER, '')) as FEED_USER
                    FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
                    WHERE LOT_NO = @latest_lot
                    GROUP BY LOT_NO, MATERIAL_BATCH, MATERIAL_NAME
                    ORDER BY MIN(FEED_TIME) ASC;
                END
                """

                async with self._engine.connect() as conn:
                    if self._disposing or self._is_disposed:
                        return []

                    result = await conn.execute(
                        text(query),
                        {"equip_code": equip_code},
                    )
                    rows = result.fetchall()

                    records = []
                    for row in rows:
                        try:
                            record = MaterialInputRecord(
                                lot_no=str(row[0]).strip() if row[0] else "",
                                material_batch=str(row[1]).strip() if row[1] else "",
                                material_name=str(row[2]).strip() if row[2] else "",
                                feed_time=self._parse_datetime(row[3]) if row[3] else datetime.now(),
                                feed_qty=float(row[4]) if row[4] else 0.0,
                                feed_user=str(row[5]).strip() if row[5] else "",
                            )
                            records.append(record)
                        except Exception as e:
                            logger.warning(f"[MssqlAdapter] Parse error: {e}")
                            continue

                    return records

            reduced_retry = RetryConfig(max_attempts=1)

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    timeout=5.0,
                    operation_name=f"fetch_material_inputs({equip_code})",
                ),
                reduced_retry,
                f"fetch_material_inputs({equip_code})",
            )
            success = True

            if result:
                logger.info(f"[MssqlAdapter] Fetched {len(result)} materials for {equip_code}")
            else:
                logger.debug(f"[MssqlAdapter] No materials found for {equip_code} in last 2 days")
            return result

        except (TimeoutError, OperationalError, ConnectionError) as e:
            if not self._is_disposed and not self._disposing:
                logger.warning(f"[MssqlAdapter] Material timeout for {equip_code}")
            return []
        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Material error: {e}")
            return []
        finally:
            await self._exit_operation(success)

    async def health_check(self) -> bool:
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
        self._circuit_breaker.reset()
        logger.info("[MssqlAdapter] Circuit breaker reset manually")

    def get_metrics(self) -> "RemoteMetrics":
        from iFactory.application.ports.remote import RemoteMetrics

        metrics = RemoteMetrics()
        metrics.total_requests = getattr(self, "_total_requests", 0)
        metrics.successful_requests = getattr(self, "_successful_requests", 0)
        metrics.failed_requests = getattr(self, "_failed_requests", 0)

        return metrics

    async def fetch_today_run_times(
        self,
        equipment_codes: List[str],
    ) -> Dict[str, float]:
        if not await self._enter_operation():
            return {code: 0.0 for code in equipment_codes}

        success = False
        try:
            if not self._engine or not equipment_codes:
                return {code: 0.0 for code in equipment_codes}

            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            async def _do_fetch():
                query_str = """
                SELECT 
                    S.EQUIP_CODE,
                    SUM(
                        DATEDIFF(
                            SECOND,
                            CASE 
                                WHEN S.START_TIME > :today_start THEN S.START_TIME 
                                ELSE :today_start 
                            END,
                            CASE 
                                WHEN S.END_TIME IS NULL THEN :now
                                WHEN S.END_TIME < :now THEN S.END_TIME
                                ELSE :now 
                            END
                        )
                    ) as run_seconds
                FROM TT_EQ_STATUS S
                WHERE S.EQUIP_CODE IN :codes
                AND S.EQUIP_STATUS = 1
                AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
                AND S.START_TIME < :now
                AND (S.END_TIME > :today_start OR S.END_TIME IS NULL)
                AND (
                    CASE 
                        WHEN S.END_TIME IS NULL THEN :now
                        WHEN S.END_TIME < :now THEN S.END_TIME
                        ELSE :now 
                    END
                    >
                    CASE 
                        WHEN S.START_TIME > :today_start THEN S.START_TIME 
                        ELSE :today_start 
                    END
                )
                GROUP BY S.EQUIP_CODE
                """

                if self._disposing:
                    return {}

                async with self._engine.connect() as conn:
                    if self._disposing:
                        return {}

                    stmt = text(query_str)
                    stmt = stmt.bindparams(bindparam("codes", expanding=True))

                    result = await conn.execute(
                        stmt,
                        {
                            "codes": tuple(equipment_codes),
                            "today_start": today_start,
                            "now": now,
                        },
                    )
                    rows = result.fetchall()

                    run_times = {code.upper(): 0.0 for code in equipment_codes}
                    for row in rows:
                        code = str(row[0]).strip().upper()
                        seconds = float(row[1]) if row[1] else 0.0
                        total_seconds_today = (now - today_start).total_seconds()
                        run_times[code] = min(max(0.0, seconds), total_seconds_today)

                    return run_times

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    operation_name="fetch_today_run_times",
                ),
                self._config.retry,
                "fetch_today_run_times",
            )
            success = True

            logger.debug(f"[MssqlAdapter] Fetched run times for {len(equipment_codes)} devices")
            return result

        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Run times fetch error: {e}")
            return {code.upper(): 0.0 for code in equipment_codes}
        finally:
            await self._exit_operation(success)

    async def fetch_single_device_run_time(
        self,
        equipment_code: str,
    ) -> float:
        if not await self._enter_operation():
            return 0.0

        success = False
        try:
            if not self._engine or not equipment_code:
                return 0.0

            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            total_seconds_today = (now - today_start).total_seconds()

            async def _do_fetch():
                query_str = """
                SELECT 
                    SUM(
                        DATEDIFF(
                            SECOND,
                            CASE 
                                WHEN S.START_TIME > :today_start THEN S.START_TIME 
                                ELSE :today_start 
                            END,
                            CASE 
                                WHEN S.END_TIME IS NULL THEN :now
                                WHEN S.END_TIME < :now THEN S.END_TIME
                                ELSE :now 
                            END
                        )
                    ) as run_seconds
                FROM TT_EQ_STATUS S
                WHERE S.EQUIP_CODE = :code
                AND S.EQUIP_STATUS = 1
                AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
                AND S.START_TIME < :now
                AND (S.END_TIME > :today_start OR S.END_TIME IS NULL)
                AND (
                    CASE 
                        WHEN S.END_TIME IS NULL THEN :now
                        WHEN S.END_TIME < :now THEN S.END_TIME
                        ELSE :now 
                    END
                    >
                    CASE 
                        WHEN S.START_TIME > :today_start THEN S.START_TIME 
                        ELSE :today_start 
                    END
                )
                """

                if self._disposing:
                    return 0.0

                async with self._engine.connect() as conn:
                    if self._disposing:
                        return 0.0

                    result = await conn.execute(
                        text(query_str),
                        {
                            "code": equipment_code.upper(),
                            "today_start": today_start,
                            "now": now,
                        },
                    )
                    row = result.fetchone()

                    if row and row[0]:
                        seconds = float(row[0])
                        return min(max(0.0, seconds), total_seconds_today)
                    return 0.0

            result = await retry_with_backoff(
                lambda: self._execute_with_timeout(
                    _do_fetch(),
                    timeout=10.0,
                    operation_name=f"fetch_run_time({equipment_code})",
                ),
                self._config.retry,
                f"fetch_run_time({equipment_code})",
            )
            success = True

            logger.debug(f"[MssqlAdapter] Run time for {equipment_code}: {result:.0f}s")
            return result

        except Exception as e:
            if not self._is_disposed and not self._disposing:
                logger.error(f"[MssqlAdapter] Run time fetch error for {equipment_code}: {e}")
            return 0.0
        finally:
            await self._exit_operation(success)

    async def dispose(self) -> None:
        if self._is_disposed:
            return

        logger.info("[MssqlAdapter] Starting disposal...")

        async with self._lock:
            self._disposing = True
            active = self._active_count

        if active > 0:
            logger.info(f"[MssqlAdapter] Waiting for {active} operations...")
            wait_time = 0
            max_wait = 3.0
            while wait_time < max_wait:
                await asyncio.sleep(0.1)
                wait_time += 0.1
                async with self._lock:
                    if self._active_count == 0:
                        break

            async with self._lock:
                if self._active_count > 0:
                    logger.warning(
                        "[MssqlAdapter] Forcing disposal with %d active operations",
                        self._active_count,
                    )

        self._is_disposed = True

        if self._engine:
            try:
                await asyncio.wait_for(self._engine.dispose(), timeout=2.0)
                logger.info("[MssqlAdapter] Engine disposed")
            except asyncio.TimeoutError:
                logger.warning("[MssqlAdapter] Engine dispose timed out")
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
    "MaterialInputRecord",
]
