"""
MSSQL data source implementation.

Implements RemoteDataSource interface for MSSQL database access.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Sequence, List, Any
from sqlalchemy import text, bindparam
from iFactory.application.interfaces import (
    RemoteDataSource,
    RemoteStatusRecord,
    RemoteInputRecord,
)
from iFactory.infrastructure.database import MSSQLEngine, DBConfig, RemoteDBParams
from ..utils import parse_datetime, load_layout, extract_codes_from_layout

__all__ = ["MssqlDataSource"]
logger = logging.getLogger(__name__)


class MssqlDataSource(RemoteDataSource):
    """
    MSSQL implementation of RemoteDataSource.

    Provides access to factory data stored in MSSQL database:
        - TT_EQ_STATUS: Device status table
        - RPT_FEEDING_DETAIL: Material feeding table
    """

    SQL_LATEST_STATUS = "\n        WITH latest AS (\n            SELECT \n                EQUIP_CODE, \n                EQUIP_STATUS, \n                START_TIME, \n                END_TIME,\n                ROW_NUMBER() OVER (\n                    PARTITION BY EQUIP_CODE\n                    ORDER BY CASE WHEN END_TIME IS NULL THEN 0 ELSE 1 END, \n                             START_TIME DESC\n                ) AS rn\n            FROM TT_EQ_STATUS \n            WHERE EQUIP_CODE IN :codes\n        )\n        SELECT EQUIP_CODE, EQUIP_STATUS, START_TIME, END_TIME \n        FROM latest \n        WHERE rn = 1\n    "
    SQL_STATUS_SINCE = "\n        SELECT \n            EQUIP_CODE, \n            EQUIP_STATUS, \n            START_TIME, \n            END_TIME,\n            DATEDIFF(SECOND, START_TIME, ISNULL(END_TIME, GETDATE())) AS DURATION_SEC\n        FROM TT_EQ_STATUS\n        WHERE EQUIP_CODE IN :codes\n          AND (\n              START_TIME >= :since \n              OR (END_TIME IS NULL OR END_TIME >= :since)\n          )\n        ORDER BY START_TIME DESC\n    "
    SQL_STATUS_HISTORY = "\n        SELECT \n            EQUIP_CODE, \n            EQUIP_STATUS, \n            START_TIME, \n            END_TIME,\n            DATEDIFF(SECOND, START_TIME, ISNULL(END_TIME, GETDATE())) AS DURATION_SEC\n        FROM TT_EQ_STATUS\n        WHERE EQUIP_CODE = :code\n          AND (\n              (START_TIME >= :start_time AND START_TIME < :end_time)\n              OR (END_TIME >= :start_time AND END_TIME < :end_time)\n              OR (START_TIME < :start_time AND (END_TIME IS NULL OR END_TIME > :end_time))\n          )\n        ORDER BY START_TIME DESC\n    "
    SQL_LATEST_INPUT = "\n        WITH latest AS (\n            SELECT \n                EQUIP_CODE, \n                MATERIAL_BATCH, \n                FEED_TIME,\n                ROW_NUMBER() OVER (\n                    PARTITION BY EQUIP_CODE \n                    ORDER BY FEED_TIME DESC\n                ) AS rn\n            FROM RPT_FEEDING_DETAIL\n            WHERE EQUIP_CODE IN :codes\n        )\n        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME \n        FROM latest \n        WHERE rn = 1\n    "
    SQL_INPUT_SINCE = "\n        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME\n        FROM RPT_FEEDING_DETAIL\n        WHERE EQUIP_CODE IN :codes\n          AND FEED_TIME >= :since\n        ORDER BY FEED_TIME DESC\n    "
    SQL_INPUT_HISTORY = "\n        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME\n        FROM RPT_FEEDING_DETAIL\n        WHERE EQUIP_CODE = :code\n          AND FEED_TIME >= :start_time\n          AND FEED_TIME < :end_time\n        ORDER BY FEED_TIME DESC\n    "
    SQL_AVAILABLE_DEVICES = (
        "\n        SELECT DISTINCT EQUIP_CODE \n        FROM TT_EQ_STATUS \n        WHERE EQUIP_CODE IS NOT NULL\n        ORDER BY EQUIP_CODE\n    "
    )
    SQL_LAST_UPDATE = "\n        SELECT MAX(START_TIME) FROM TT_EQ_STATUS\n    "
    __slots__ = ("_engine", "_config", "_remote_params")

    def __init__(
        self,
        engine: Optional[MSSQLEngine] = None,
        remote_params: Optional[RemoteDBParams] = None,
        config: Optional[DBConfig] = None,
    ):
        """
        Initialize data source.

        Args:
            engine: Existing MSSQL engine (optional)
            remote_params: Connection parameters (if no engine provided)
            config: Database configuration
        """
        self._engine = engine
        self._config = config or DBConfig()
        self._remote_params = remote_params or RemoteDBParams()

    async def connect(self) -> None:
        """Establish connection to MSSQL."""
        if self._engine is None:
            self._engine = MSSQLEngine(remote=self._remote_params, config=self._config, name="RemoteDataSource")
        if not self._engine.is_connected:
            await self._engine.connect()

    async def disconnect(self) -> None:
        """Close connection."""
        if self._engine:
            await self._engine.disconnect()

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._engine is not None and self._engine.is_connected

    async def _ensure_connected(self) -> bool:
        """Ensure connection exists, try to connect if not."""
        if self._engine is None:
            return False
        if not self._engine.is_connected:
            try:
                await asyncio.to_thread(self._engine._engine.connect)
                self._engine.is_connected = True
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                return False
        return self._engine.is_connected

    async def health_check(self) -> bool:
        """Perform health check."""
        if not await self._ensure_connected():
            return False
        status = await self._engine.health_check()
        return status.healthy

    @property
    def engine(self) -> Optional[MSSQLEngine]:
        """Get underlying engine."""
        return self._engine

    async def _run_query(self, stmt: str | text, params: Optional[dict] = None) -> List[Any]:
        """
        Helper to run synchronous SQLAlchemy queries in a separate thread.

        Args:
            stmt: SQL statement string or SQLAlchemy text object
            params: Dictionary of parameters

        Returns:
            List of result rows
        """
        if not await self._ensure_connected():
            logger.warning("[MssqlDataSource] Not connected")
            return []

        def _execute():
            with self._engine._engine.connect() as conn:
                return conn.execute(stmt, params or {}).fetchall()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error(f"[MssqlDataSource] Query error: {e}")
            return []

    async def fetch_latest_status(self, codes: Optional[Sequence[str]] = None) -> Sequence[RemoteStatusRecord]:
        """Fetch latest status for devices."""
        if not codes:
            codes = extract_codes_from_layout(load_layout())
        if not codes:
            return []
        stmt = text(self.SQL_LATEST_STATUS).bindparams(bindparam("codes", expanding=True))
        rows = await self._run_query(stmt, {"codes": list(codes)})
        now = datetime.now()
        records = []
        for row in rows:
            records.append(
                RemoteStatusRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    equip_status=str(row[1]) if row[1] else "0",
                    start_time=parse_datetime(row[2]),
                    end_time=parse_datetime(row[3]),
                    last_update=parse_datetime(row[2] if row[3] is None else row[3]) or now,
                    create_date=now,
                )
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} latest status")
        return records

    async def fetch_status_since(self, since: datetime, codes: Optional[Sequence[str]] = None) -> Sequence[RemoteStatusRecord]:
        """Fetch status records changed since timestamp."""
        if not codes:
            codes = extract_codes_from_layout(load_layout())
        if not codes:
            return []
        stmt = text(self.SQL_STATUS_SINCE).bindparams(bindparam("codes", expanding=True))
        rows = await self._run_query(stmt, {"codes": list(codes), "since": since})
        records = []
        for row in rows:
            start_time = parse_datetime(row[2])
            if not start_time:
                continue
            records.append(
                RemoteStatusRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    equip_status=str(row[1]) if row[1] else "0",
                    start_time=start_time,
                    end_time=parse_datetime(row[3]),
                    last_update=start_time,
                )
            )
        logger.info(f"[MssqlDataSource] Fetched {len(records)} status since {since}")
        return records

    async def fetch_status_history(self, code: str, start: datetime, end: datetime) -> Sequence[RemoteStatusRecord]:
        """Fetch status history for a device in time range."""
        stmt = text(self.SQL_STATUS_HISTORY)
        rows = await self._run_query(stmt, {"code": code, "start_time": start, "end_time": end})
        records = []
        for row in rows:
            start_time = parse_datetime(row[2])
            if not start_time:
                continue
            records.append(
                RemoteStatusRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    equip_status=str(row[1]) if row[1] else "0",
                    start_time=start_time,
                    end_time=parse_datetime(row[3]),
                    last_update=start_time,
                )
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} history for {code}")
        return records

    async def fetch_latest_input(self, codes: Optional[Sequence[str]] = None) -> Sequence[RemoteInputRecord]:
        """Fetch latest input for devices."""
        if not codes:
            codes = extract_codes_from_layout(load_layout())
        if not codes:
            return []
        stmt = text(self.SQL_LATEST_INPUT).bindparams(bindparam("codes", expanding=True))
        rows = await self._run_query(stmt, {"codes": list(codes)})
        now = datetime.now()
        records = []
        for row in rows:
            feeding_time = parse_datetime(row[2])
            if not feeding_time:
                continue
            records.append(
                RemoteInputRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    material_batch=str(row[1]) if row[1] else "",
                    feeding_time=feeding_time,
                    create_date=now,
                )
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} latest input")
        return records

    async def fetch_input_since(self, since: datetime, codes: Optional[Sequence[str]] = None) -> Sequence[RemoteInputRecord]:
        """Fetch input records created since timestamp."""
        if not codes:
            codes = extract_codes_from_layout(load_layout())
        if not codes:
            return []
        stmt = text(self.SQL_INPUT_SINCE).bindparams(bindparam("codes", expanding=True))
        rows = await self._run_query(stmt, {"codes": list(codes), "since": since})
        records = []
        for row in rows:
            feeding_time = parse_datetime(row[2])
            if not feeding_time:
                continue
            records.append(
                RemoteInputRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    material_batch=str(row[1]) if row[1] else "",
                    feeding_time=feeding_time,
                )
            )
        logger.info(f"[MssqlDataSource] Fetched {len(records)} input since {since}")
        return records

    async def fetch_input_history(self, code: str, start: datetime, end: datetime) -> Sequence[RemoteInputRecord]:
        """Fetch input history for a device in time range."""
        stmt = text(self.SQL_INPUT_HISTORY)
        rows = await self._run_query(stmt, {"code": code, "start_time": start, "end_time": end})
        records = []
        for row in rows:
            feeding_time = parse_datetime(row[2])
            if not feeding_time:
                continue
            records.append(
                RemoteInputRecord(
                    equip_code=str(row[0]) if row[0] else "",
                    material_batch=str(row[1]) if row[1] else "",
                    feeding_time=feeding_time,
                )
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} input history for {code}")
        return records

    async def get_available_devices(self) -> Sequence[str]:
        """Get list of all available device codes."""
        rows = await self._run_query(text(self.SQL_AVAILABLE_DEVICES))
        return [str(row[0]) for row in rows if row[0]]

    async def get_last_update_time(self) -> Optional[datetime]:
        """Get timestamp of most recent data update."""
        rows = await self._run_query(text(self.SQL_LAST_UPDATE))
        if rows and rows[0]:
            return parse_datetime(rows[0][0])
        return None
