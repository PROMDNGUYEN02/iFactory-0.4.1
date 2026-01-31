# File: application/queries/history.py
"""
History Queries (Cold Storage).
Read-only operations for historical data and Gantt charts.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Callable, Optional

from iFactory.application.common.dtos import DeviceHistoryDTO, GanttSegmentDTO
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.ports.uow import AbstractUnitOfWork

logger = logging.getLogger(__name__)


class GetDeviceHistoryQuery:
    """QUERY: Fetches raw history logs."""

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork], cache: ICacheProvider):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equip_code: str,
        days: int = 1,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[DeviceHistoryDTO]:

        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=days)

        cache_key = f"history_{equip_code}_{days}d_{start_time.date().isoformat()}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        try:
            async with self._uow_factory() as uow:
                if not uow.history:
                    logger.warning(f"No history repository for {equip_code}")
                    return []

                logger.debug(f"Querying history for {equip_code}: {start_time} to {end_time}")
                periods = await uow.history.get_history(equip_code, start_time, end_time)
                logger.debug(f"Found {len(periods)} history records for {equip_code}")

            results = [
                DeviceHistoryDTO(
                    equip_code=p.device_code,
                    status_code=str(p.status_code),
                    timestamp=p.start_time,
                    status_name=p.status_name,
                    end_time=p.end_time,
                )
                for p in periods
            ]

            await self._cache.set(cache_key, results, ttl=60)
            return results

        except Exception as e:
            logger.error(f"Failed to get history for {equip_code}: {e}", exc_info=True)
            return []


class GenerateProductionTimelineQuery:
    """QUERY: Generates formatted Gantt chart segments."""

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork], cache: ICacheProvider):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
        fill_gaps: bool = True,
    ) -> List[GanttSegmentDTO]:

        cache_key = f"timeline_{equip_code}_{start_time.date().isoformat()}_{end_time.date().isoformat()}"
        cached = await self._cache.get(cache_key)
        if cached:
            logger.debug(f"Gantt cache hit for {equip_code}")
            return cached

        try:
            async with self._uow_factory() as uow:
                if not uow.history:
                    logger.warning(f"No history repository for timeline query: {equip_code}")
                    return []

                logger.debug(f"Generating timeline for {equip_code}: {start_time} to {end_time}")
                history = await uow.history.get_history(equip_code, start_time, end_time)
                logger.info(f"Timeline query found {len(history)} records for {equip_code}")

            segments = []
            for h in history:
                seg_end = h.end_time if h.end_time else end_time
                valid_start = max(h.start_time, start_time)
                valid_end = min(seg_end, end_time)

                if valid_start < valid_end:
                    duration = (valid_end - valid_start).total_seconds()
                    segments.append(
                        GanttSegmentDTO(
                            equip_code=h.device_code,
                            status_code=str(h.status_code),
                            status_name=h.status_name,
                            start_time=valid_start,
                            end_time=valid_end,
                            duration_seconds=duration,
                            percent=0.0,
                        )
                    )

            if segments:
                await self._cache.set(cache_key, segments, ttl=30)
                logger.debug(f"Cached {len(segments)} segments for {equip_code}")

            return segments

        except Exception as e:
            logger.error(f"Failed to generate timeline for {equip_code}: {e}", exc_info=True)
            return []


__all__ = ["GetDeviceHistoryQuery", "GenerateProductionTimelineQuery"]
