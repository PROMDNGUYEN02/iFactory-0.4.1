import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class MssqlDataSource(IRemoteDataSource):
    def __init__(self, connection_string: str):
        if "TrustServerCertificate" not in connection_string:
            connection_string += "&TrustServerCertificate=yes"
        self._engine = create_async_engine(connection_string, pool_pre_ping=True, echo=False)

    def _parse_datetime(self, val: Any) -> datetime:
        """Helper để convert dữ liệu thời gian từ SQL sang Python datetime."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                # Cắt bớt phần nano giây dư thừa nếu có (MSSQL thường có 7 chữ số sau dấu chấm)
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except Exception:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return datetime.now()
        return datetime.now()

    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
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
                    # Mapping chính xác dựa trên kết quả debug
                    data.append(
                        {
                            "equip_code": str(row[0]).strip(),
                            "equip_status": str(row[1]),
                            "raw_status": str(row[1]),
                            "last_update": self._parse_datetime(row[2]),  # Ép kiểu datetime chuẩn
                        }
                    )

                if data:
                    logger.info(f"[MssqlDataSource] Fetched {len(data)} records from MSSQL.")
                return data

        except Exception as e:
            logger.error(f"[MssqlDataSource] Error: {e}")
            return []

    async def fetch_device_status(self, equip_code: str) -> Optional[Dict[str, Any]]:
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
            logger.error(f"[MssqlDataSource] Error device {equip_code}: {e}")
            return None

    async def dispose(self):
        await self._engine.dispose()
