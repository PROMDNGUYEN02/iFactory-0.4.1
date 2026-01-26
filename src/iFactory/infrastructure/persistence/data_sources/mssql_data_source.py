"""
MSSQL data source implementation.

Implements IRemoteDataSource interface for MSSQL database access.
Acts as an Anti-Corruption Layer (ACL) translating legacy DB codes to Domain business terms.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Optional, Sequence, List, Any, Dict
from sqlalchemy import text, bindparam

# Sửa lại import: Sử dụng IRemoteDataSource (có chữ "I") thay vì RemoteDataSource
from iFactory.application.interfaces import IRemoteDataSource

from iFactory.infrastructure.database import MSSQLEngine, DBConfig, RemoteDBParams
from ..utils import parse_datetime, load_layout, extract_codes_from_layout

__all__ = ["MssqlDataSource"]
logger = logging.getLogger(__name__)


class MssqlDataSource(IRemoteDataSource):
    """
    MSSQL implementation of IRemoteDataSource.

    Provides access to factory data stored in MSSQL database:
        - TT_EQ_STATUS: Device status table
        - RPT_FEEDING_DETAIL: Material feeding table
    """

    SQL_LATEST_STATUS = """
        WITH latest AS (
            SELECT 
                EQUIP_CODE, 
                EQUIP_STATUS, 
                START_TIME, 
                END_TIME,
                ROW_NUMBER() OVER (
                    PARTITION BY EQUIP_CODE
                    ORDER BY CASE WHEN END_TIME IS NULL THEN 0 ELSE 1 END, 
                             START_TIME DESC
                ) AS rn
            FROM TT_EQ_STATUS 
            WHERE EQUIP_CODE IN :codes
        )
        SELECT EQUIP_CODE, EQUIP_STATUS, START_TIME, END_TIME 
        FROM latest 
        WHERE rn = 1
    """
    SQL_STATUS_SINCE = """
        SELECT 
            EQUIP_CODE, 
            EQUIP_STATUS, 
            START_TIME, 
            END_TIME,
            DATEDIFF(SECOND, START_TIME, ISNULL(END_TIME, GETDATE())) AS DURATION_SEC
        FROM TT_EQ_STATUS
        WHERE EQUIP_CODE IN :codes
          AND (
              START_TIME >= :since 
              OR (END_TIME IS NULL OR END_TIME >= :since)
          )
        ORDER BY START_TIME DESC
    """
    SQL_STATUS_HISTORY = """
        SELECT 
            EQUIP_CODE, 
            EQUIP_STATUS, 
            START_TIME, 
            END_TIME,
            DATEDIFF(SECOND, START_TIME, ISNULL(END_TIME, GETDATE())) AS DURATION_SEC
        FROM TT_EQ_STATUS
        WHERE EQUIP_CODE = :code
          AND (
              (START_TIME >= :start_time AND START_TIME < :end_time)
              OR (END_TIME >= :start_time AND END_TIME < :end_time)
              OR (START_TIME < :start_time AND (END_TIME IS NULL OR END_TIME > :end_time))
          )
        ORDER BY START_TIME DESC
    """
    SQL_LATEST_INPUT = """
        WITH latest AS (
            SELECT 
                EQUIP_CODE, 
                MATERIAL_BATCH, 
                FEED_TIME,
                ROW_NUMBER() OVER (
                    PARTITION BY EQUIP_CODE 
                    ORDER BY FEED_TIME DESC
                ) AS rn
            FROM RPT_FEEDING_DETAIL
            WHERE EQUIP_CODE IN :codes
        )
        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME 
        FROM latest 
        WHERE rn = 1
    """
    SQL_INPUT_SINCE = """
        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME
        FROM RPT_FEEDING_DETAIL
        WHERE EQUIP_CODE IN :codes
          AND FEED_TIME >= :since
        ORDER BY FEED_TIME DESC
    """
    SQL_INPUT_HISTORY = """
        SELECT EQUIP_CODE, MATERIAL_BATCH, FEED_TIME
        FROM RPT_FEEDING_DETAIL
        WHERE EQUIP_CODE = :code
          AND FEED_TIME >= :start_time
          AND FEED_TIME < :end_time
        ORDER BY FEED_TIME DESC
    """
    SQL_AVAILABLE_DEVICES = """
        SELECT DISTINCT EQUIP_CODE 
        FROM TT_EQ_STATUS 
        WHERE EQUIP_CODE IS NOT NULL
        ORDER BY EQUIP_CODE
    """
    SQL_LAST_UPDATE = """
        SELECT MAX(START_TIME) FROM TT_EQ_STATUS
    """

    # Mapping legacy DB codes to Domain "MachineStatus" business terms
    _STATUS_MAPPING = {
        "0": "unknown",
        "1": "running",
        "2": "shutdown",
        "3": "stopped",
        "4": "maintenance",
        "5": "alarm",
    }

    __slots__ = ("_engine", "_config", "_remote_params")

    def __init__(
        self,
        engine: Optional[MSSQLEngine] = None,
        remote_params: Optional[RemoteDBParams] = None,
        config: Optional[DBConfig] = None,
    ):
        self._engine = engine
        self._config = config or DBConfig()
        self._remote_params = remote_params or RemoteDBParams()

    def _map_db_status(self, raw_status: Any) -> str:
        """Anti-corruption: Maps raw numeric DB status to Domain business term."""
        if raw_status is None:
            return "unknown"
        return self._STATUS_MAPPING.get(str(raw_status).strip(), "unknown")

    async def connect(self) -> None:
        if self._engine is None:
            self._engine = MSSQLEngine(remote=self._remote_params, config=self._config, name="RemoteDataSource")
        if not self._engine.is_connected:
            await self._engine.connect()

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.disconnect()

    async def is_connected(self) -> bool:
        return self._engine is not None and self._engine.is_connected

    async def _ensure_connected(self) -> bool:
        if self._engine is None:
            return False
        if not self._engine.is_connected:
            try:
                await self._engine.connect()
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                return False
        return self._engine.is_connected

    async def health_check(self) -> bool:
        if not await self._ensure_connected():
            return False
        status = await self._engine.health_check()
        return status.healthy

    @property
    def engine(self) -> Optional[MSSQLEngine]:
        return self._engine

    async def _run_query(self, stmt: str | text, params: Optional[dict] = None) -> List[Any]:
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

    # === IRemoteDataSource Implementation ===

    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        """Fetch latest status for a single device to satisfy IRemoteDataSource."""
        results = await self.fetch_latest_status([equip_code])
        return results[0] if results else {"equip_code": equip_code, "equip_status": "unknown"}

    # === Extended Batch Fetching Methods ===

    async def fetch_latest_status(self, codes: Optional[Sequence[str]] = None) -> Sequence[Dict[str, Any]]:
        """Fetch latest status for devices (returns raw dicts)."""
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
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "equip_status": self._map_db_status(row[1]),
                    "start_time": parse_datetime(row[2]),
                    "end_time": parse_datetime(row[3]),
                    "last_update": parse_datetime(row[2] if row[3] is None else row[3]) or now,
                }
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} latest status")
        return records

    async def fetch_status_since(self, since: datetime, codes: Optional[Sequence[str]] = None) -> Sequence[Dict[str, Any]]:
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
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "equip_status": self._map_db_status(row[1]),
                    "start_time": start_time,
                    "end_time": parse_datetime(row[3]),
                    "last_update": start_time,
                }
            )
        logger.info(f"[MssqlDataSource] Fetched {len(records)} status since {since}")
        return records

    async def fetch_status_history(self, code: str, start: datetime, end: datetime) -> Sequence[Dict[str, Any]]:
        """Fetch status history for a device in time range."""
        stmt = text(self.SQL_STATUS_HISTORY)
        rows = await self._run_query(stmt, {"code": code, "start_time": start, "end_time": end})
        records = []
        for row in rows:
            start_time = parse_datetime(row[2])
            if not start_time:
                continue
            records.append(
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "equip_status": self._map_db_status(row[1]),
                    "start_time": start_time,
                    "end_time": parse_datetime(row[3]),
                    "last_update": start_time,
                }
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} history for {code}")
        return records

    async def fetch_latest_input(self, codes: Optional[Sequence[str]] = None) -> Sequence[Dict[str, Any]]:
        """Fetch latest input for devices."""
        if not codes:
            codes = extract_codes_from_layout(load_layout())
        if not codes:
            return []
        stmt = text(self.SQL_LATEST_INPUT).bindparams(bindparam("codes", expanding=True))
        rows = await self._run_query(stmt, {"codes": list(codes)})
        records = []
        for row in rows:
            feeding_time = parse_datetime(row[2])
            if not feeding_time:
                continue
            records.append(
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "material_batch": str(row[1]) if row[1] else "",
                    "feeding_time": feeding_time,
                }
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} latest input")
        return records

    async def fetch_input_since(self, since: datetime, codes: Optional[Sequence[str]] = None) -> Sequence[Dict[str, Any]]:
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
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "material_batch": str(row[1]) if row[1] else "",
                    "feeding_time": feeding_time,
                }
            )
        logger.info(f"[MssqlDataSource] Fetched {len(records)} input since {since}")
        return records

    async def fetch_input_history(self, code: str, start: datetime, end: datetime) -> Sequence[Dict[str, Any]]:
        """Fetch input history for a device in time range."""
        stmt = text(self.SQL_INPUT_HISTORY)
        rows = await self._run_query(stmt, {"code": code, "start_time": start, "end_time": end})
        records = []
        for row in rows:
            feeding_time = parse_datetime(row[2])
            if not feeding_time:
                continue
            records.append(
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "material_batch": str(row[1]) if row[1] else "",
                    "feeding_time": feeding_time,
                }
            )
        logger.debug(f"[MssqlDataSource] Fetched {len(records)} input history for {code}")
        return records

    async def get_available_devices(self) -> Sequence[str]:
        rows = await self._run_query(text(self.SQL_AVAILABLE_DEVICES))
        return [str(row[0]) for row in rows if row[0]]

    async def get_last_update_time(self) -> Optional[datetime]:
        rows = await self._run_query(text(self.SQL_LAST_UPDATE))
        if rows and rows[0]:
            return parse_datetime(rows[0][0])
