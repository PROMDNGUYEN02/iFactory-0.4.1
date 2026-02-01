"""
MSSQL Adapter.
Implements IRemoteDataSource for MSSQL/SCADA database.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.pool import NullPool

from iFactory.application.ports.remote import IRemoteDataSource

logger = logging.getLogger(__name__)


class MssqlAdapter(IRemoteDataSource):
    """
    Adapter for External MSSQL PLC/SCADA Database.
    Optimized for page-based selective syncing.
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._connection_string = connection_string
        self._is_disposed = False

        if connection_string:
            self._engine = create_async_engine(
                connection_string,
                poolclass=NullPool,
                echo=False,
            )

    def _parse_datetime(self, val: Any) -> datetime:
        """Robust datetime parsing for legacy SQL types."""
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
        """Maps raw SQL tuple to dictionary."""
        equip_code = str(row[0]).strip() if row[0] else "UNKNOWN"
        equip_status = str(row[1]) if row[1] else "0"
        start_time = self._parse_datetime(row[2])
        end_time_val = row[3]
        reason_code = str(row[4]).strip() if row[4] else None
        equip_name = str(row[5]).strip() if row[5] else None

        if end_time_val:
            last_update = self._parse_datetime(end_time_val)
        else:
            last_update = datetime.now()

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
        """
        Fetch the single LATEST status for specified devices.
        """
        if self._is_disposed or not self._engine:
            logger.warning("MSSQL Engine not initialized or disposed.")
            return []

        if equipment_codes is not None and len(equipment_codes) == 0:
            return []

        # Build filter clause
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

        try:
            async with self._engine.connect() as conn:
                stmt = text(query_str)
                if equipment_codes:
                    stmt = stmt.bindparams(bindparam("codes", expanding=True))

                result = await conn.execute(stmt, params)
                rows = result.fetchall()

                return [self._map_row(row) for row in rows]

        except Exception as e:
            if not self._is_disposed:
                logger.error(f"[MssqlAdapter] Bulk fetch error: {e}")
            return []

    async def fetch_device_status(
        self,
        equip_code: str,
        days: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch history status for a single device."""
        if self._is_disposed:
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
        """Fetch history for a specific time range."""
        if self._is_disposed or not self._engine:
            return []

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

        try:
            async with self._engine.connect() as conn:
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

        except Exception as e:
            if not self._is_disposed:
                logger.error(f"[MssqlAdapter] History fetch error for {equip_code}: {e}")
            return []

    async def fetch_latest_history_records(
        self,
        equip_code: str,
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """Fetch the N most recent history records for a device."""
        if self._is_disposed or not self._engine:
            return []

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

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(
                    text(query),
                    {"code": equip_code, "limit": limit},
                )
                rows = result.fetchall()
                return [self._map_row(row) for row in rows]

        except Exception as e:
            if not self._is_disposed:
                logger.error(f"[MssqlAdapter] Latest history error for {equip_code}: {e}")
            return []

    async def dispose(self) -> None:
        """Clean up engine."""
        self._is_disposed = True

        if self._engine:
            try:
                await self._engine.dispose()
                logger.info("[MssqlAdapter] Engine disposed")
            except Exception as e:
                logger.warning(f"Error disposing MSSQL engine: {e}")
            finally:
                self._engine = None


__all__ = ["MssqlAdapter"]
