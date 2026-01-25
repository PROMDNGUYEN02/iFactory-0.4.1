"""
Use Case: Sinh timeline Gantt cho thiết bị.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from iFactory.application.config.constants import CacheDefaults, CacheKeys
from iFactory.application.dtos import GanttSegmentDTO
from iFactory.application.interfaces import CacheProvider, UnitOfWork
from iFactory.application.mappers import StatusPeriodMapper
from iFactory.domain.value_objects import EquipmentCode, TimeRange

logger = logging.getLogger(__name__)


class GenerateProductionTimelineUseCase:
    """Use Case sinh timeline sản xuất."""

    def __init__(
        self,
        unit_of_work_factory: callable,
        cache_provider: Optional[CacheProvider] = None,
    ):
        self._uow_factory = unit_of_work_factory
        self._cache = cache_provider

    async def execute(
        self,
        equipment_code: str,
        start_time: datetime,
        end_time: datetime,
        fill_gaps: bool = True,
    ) -> list[GanttSegmentDTO]:
        try:
            code_vo = EquipmentCode(equipment_code)
            range_vo = TimeRange(start=start_time, end=end_time)
        except ValueError as e:
            logger.error(f"[GanttUseCase] Invalid input params: {e}")
            return []

        cache_key = CacheKeys.gantt_segments(equipment_code, str(start_time.date()))

        if self._cache:
            try:
                cached_data = await self._cache.get(cache_key)
                if cached_data:
                    logger.debug(f"[GanttUseCase] Cache HIT for {equipment_code}")
                    segments = [GanttSegmentDTO.from_dict(item) if isinstance(item, dict) else item for item in cached_data]
                    return segments
            except Exception as e:
                logger.warning(f"[GanttUseCase] Cache GET failed: {e}")

        segments: list[GanttSegmentDTO] = []
        mapper = StatusPeriodMapper()

        async with self._uow_factory() as uow:
            try:
                history_entities = await uow.statuses.get_history(code_vo, range_vo)
                segments = [mapper.to_dto(entity, theme="light") for entity in history_entities]
            except Exception as e:
                logger.error(f"[GanttUseCase] Failed to fetch history: {e}")
                return []

        if fill_gaps:
            segments = self._fill_gaps(segments, range_vo.start, range_vo.end)
        segments.sort(key=lambda s: s.start_time)

        if self._cache and segments:
            try:
                await self._cache.set(cache_key, [s.to_dict() for s in segments], ttl=timedelta(seconds=CacheDefaults.TTL_GANTT))
            except Exception as e:
                logger.warning(f"[GanttUseCase] Cache SET failed: {e}")

        return segments

    def _fill_gaps(self, segments: list[GanttSegmentDTO], range_start: datetime, range_end: datetime) -> list[GanttSegmentDTO]:
        """Private helper: Điền vào các khoảng trống thời gian."""
        if not segments:
            return [self._create_unknown_segment(range_start, range_end)]

        filled: list[GanttSegmentDTO] = []
        segments.sort(key=lambda s: s.start_time)

        if segments[0].start_time > range_start:
            filled.append(self._create_unknown_segment(range_start, segments[0].start_time))

        for i, seg in enumerate(segments):
            filled.append(seg)
            if i < len(segments) - 1:
                current_end = seg.end_time
                next_start = segments[i + 1].start_time
                if current_end < next_start:
                    filled.append(self._create_unknown_segment(current_end, next_start))

        if segments[-1].end_time < range_end:
            filled.append(self._create_unknown_segment(segments[-1].end_time, range_end))

        return filled

    def _create_unknown_segment(self, start: datetime, end: datetime) -> GanttSegmentDTO:
        color = "#9E9E9E"
        return GanttSegmentDTO(
            start_time=start,
            end_time=end,
            status_code="0",
            status_name="unknown",
            status_color=color,
        )
