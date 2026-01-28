"""
Infrastructure: MSSQL Adapter.
Implements IRemoteDataSource for external database communication.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from iFactory.application.ports.remote_data_source import IRemoteDataSource

# UPDATED: Import shared engine factory to eliminate duplication
from iFactory.infrastructure.persistence.sqlalchemy.database import get_mssql_engine

logger = logging.getLogger(__name__)


class MssqlAdapter(IRemoteDataSource):
    """
    Adapter for MSSQL Server.
    Fetches raw status data and converts to dictionary format.
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        """
        Args:
            connection_string: Optional. If None, uses the shared application engine.
        """
        if connection_string:
            # Create a dedicated engine if a specific connection string is provided (e.g., testing)
            if "TrustServerCertificate" not in connection_string:
                connection_string += "&TrustServerCertificate=yes"
            self._engine = create_async_engine(connection_string, pool_pre_ping=True, echo=False)
        else:
            # Use the shared singleton engine from the infrastructure layer
            self._engine = get_mssql_engine()

        if self._engine is None:
            logger.warning("MSSQL configuration missing. Adapter disabled.")

    def _parse_datetime(self, val: Any) -> datetime:
        """Helper to convert SQL datetime types to Python datetime."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                # Truncate excessive nanoseconds if present
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return datetime.now()
        return datetime.now()

    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if not self._engine:
            return []

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

                data = []
                for row in rows:
                    data.append(
                        {
                            "equip_code": str(row[0]).strip(),
                            "equip_status": str(row[1]),
                            "raw_status": str(row[1]),
                            "last_update": self._parse_datetime(row[2]),
                        }
                    )

                if data:
                    logger.info(f"[MssqlAdapter] Fetched {len(data)} records.")
                return data

        except Exception as e:
            logger.error(f"[MssqlAdapter] Fetch error: {e}")
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
            logger.error(f"[MssqlAdapter] Error device {equip_code}: {e}")
            return None

    async def dispose(self) -> None:
        if self._engine:
            # We don't dispose the shared engine here as it's managed by the DI container / app lifecycle
            pass
