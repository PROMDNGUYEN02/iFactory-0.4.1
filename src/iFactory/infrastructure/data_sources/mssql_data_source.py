"""
MSSQL Data Source Adapter.
Fetches raw primitive data. Does not interpret business meaning.
"""

from __future__ import annotations
import logging
from typing import Sequence, Dict, Any
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import create_async_engine

from iFactory.application.interfaces.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class MssqlDataSource(IRemoteDataSource):
    """
    MSSQL implementation of IRemoteDataSource.
    Returns primitive RAW dictionaries. Translation to Domain logic happens in the Application Layer.
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

    def __init__(self, connection_string: str):
        self._engine = create_async_engine(connection_string, echo=False)

    async def fetch_latest_status(self, codes: Sequence[str]) -> Sequence[Dict[str, Any]]:
        if not codes:
            return []

        stmt = text(self.SQL_LATEST_STATUS).bindparams(bindparam("codes", expanding=True))

        async with self._engine.connect() as conn:
            result = await conn.execute(stmt, {"codes": list(codes)})
            rows = result.fetchall()

        return [
            {
                "equip_code": str(row[0]) if row[0] else "",
                "raw_status": str(row[1]) if row[1] is not None else "",
                "start_time": row[2],
                "end_time": row[3],
            }
            for row in rows
        ]

    async def fetch_all_devices(self) -> Sequence[Dict[str, Any]]:
        async with self._engine.connect() as conn:
            result = await conn.execute(text("SELECT DISTINCT EQUIP_CODE FROM TT_EQ_STATUS WHERE EQUIP_CODE IS NOT NULL"))
            actual_codes = [str(row[0]) for row in result.fetchall()]

            if not actual_codes:
                return []

        return await self.fetch_latest_status(actual_codes)

    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        results = await self.fetch_latest_status([equip_code])
        return results[0] if results else {"equip_code": equip_code, "raw_status": "unknown"}

    async def dispose(self) -> None:
        await self._engine.dispose()
