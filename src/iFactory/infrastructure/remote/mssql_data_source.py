from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Optional, Sequence, Dict, Any
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine

from iFactory.application.interfaces.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class MssqlDataSource(IRemoteDataSource):
    """
    MSSQL implementation of IRemoteDataSource.
    Strictly translates legacy data into raw application dictionaries.
    NO UI or Domain logic included.
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

    _STATUS_MAPPING = {
        "0": "unknown",
        "1": "running",
        "2": "shutdown",
        "3": "stopped",
        "4": "maintenance",
        "5": "alarm",
    }

    def __init__(self, connection_string: str):
        self._engine = create_async_engine(connection_string, echo=False)

    def _map_db_status(self, raw_status: Any) -> str:
        if raw_status is None:
            return "unknown"
        return self._STATUS_MAPPING.get(str(raw_status).strip(), "unknown")

    async def fetch_latest_status(self, codes: Sequence[str]) -> Sequence[Dict[str, Any]]:
        """Fetch latest status for given devices."""
        if not codes:
            return []

        stmt = text(self.SQL_LATEST_STATUS).bindparams(bindparam("codes", expanding=True))

        async with self._engine.connect() as conn:
            result = await conn.execute(stmt, {"codes": list(codes)})
            rows = result.fetchall()

        now = datetime.now()
        records = []
        for row in rows:
            records.append(
                {
                    "equip_code": str(row[0]) if row[0] else "",
                    "equip_status": self._map_db_status(row[1]),
                    "start_time": row[2],
                    "end_time": row[3],
                    "last_update": row[2] if row[3] is None else row[3] or now,
                }
            )

        return records

    async def fetch_all_devices(self) -> Sequence[Dict[str, Any]]:
        """
        Fetches the latest status for ALL available devices.
        Satisfies the IRemoteDataSource interface.
        """
        async with self._engine.connect() as conn:
            codes_result = await conn.execute(text("SELECT DISTINCT EQUIP_CODE FROM TT_EQ_STATUS WHERE EQUIP_CODE IS NOT NULL"))
            actual_codes = [str(row[0]) for row in codes_result.fetchall()]

            if not actual_codes:
                return []

        return await self.fetch_latest_status(actual_codes)

    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        results = await self.fetch_latest_status([equip_code])
        return results[0] if results else {"equip_code": equip_code, "equip_status": "unknown"}

    async def dispose(self) -> None:
        await self._engine.dispose()
