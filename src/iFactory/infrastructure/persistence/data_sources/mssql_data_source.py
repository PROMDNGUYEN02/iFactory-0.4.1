import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncEngine
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class MssqlDataSource(IRemoteDataSource):
    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        logger.info(f"Fetching from MSSQL: {equip_code}")
        # Giả lập trả về dữ liệu DB
        return {"equip_code": equip_code, "equip_status": "1", "last_update": None}
