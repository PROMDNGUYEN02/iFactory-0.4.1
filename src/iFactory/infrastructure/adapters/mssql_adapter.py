import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from iFactory.application.ports.remote import IRemoteDataSource

# Assuming database factory is available here, or injected.
from iFactory.infrastructure.persistence.sqlalchemy.database import get_mssql_engine

logger = logging.getLogger(__name__)


class MssqlAdapter(IRemoteDataSource):
    """
    Adapter for External MSSQL PLC/SCADA Database.
    Responsible ONLY for fetching raw data. No business logic.
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self._engine: Optional[AsyncEngine] = None
        if connection_string:
            self._engine = create_async_engine(connection_string, pool_pre_ping=True, echo=False)
        else:
            self._engine = get_mssql_engine()

    def _parse_datetime(self, val: Any) -> datetime:
        """Robust datetime parsing for legacy SQL types."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                # Handle SQL Server high-precision strings
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.now()
        return datetime.now()

    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if not self._engine:
            logger.warning("MSSQL Engine not initialized.")
            return []

        # Raw SQL used here as this is an adapter for a legacy/external schema
        query = """
        WITH RankedStatus AS (
            SELECT 
                EQUIP_CODE, EQUIP_STATUS, START_TIME,
                ROW_NUMBER() OVER (PARTITION BY EQUIP_CODE ORDER BY START_TIME DESC) as rn
            FROM TT_EQ_STATUS
            WHERE DEL_FLAG = '0' OR DEL_FLAG IS NULL
        )
        SELECT EQUIP_CODE, EQUIP_STATUS, START_TIME
        FROM RankedStatus
        WHERE rn = 1
        """

        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(query))
                rows = result.fetchall()

                return [
                    {
                        "equip_code": str(row[0]).strip(),
                        "equip_status": str(row[1]),
                        "raw_status": str(row[1]),
                        "last_update": self._parse_datetime(row[2]),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"[MssqlAdapter] Bulk fetch error: {e}")
            return []

    async def fetch_device_status(self, equip_code: str) -> Optional[Dict[str, Any]]:
        if not self._engine:
            return None

        query = """
        SELECT TOP 1 EQUIP_CODE, EQUIP_STATUS, START_TIME
        FROM TT_EQ_STATUS
        WHERE EQUIP_CODE = :code
        ORDER BY START_TIME DESC
        """
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(query), {"code": equip_code})
                row = result.fetchone()
                if row:
                    return {
                        "equip_code": str(row[0]).strip(),
                        "equip_status": str(row[1]),
                        "raw_status": str(row[1]),
                        "last_update": self._parse_datetime(row[2]),
                    }
                return None
        except Exception as e:
            logger.error(f"[MssqlAdapter] Single fetch error for {equip_code}: {e}")
            return None
