"""Get device status history use case."""

import logging
from datetime import datetime
from iFactory.application.dtos import GanttSegmentDTO
from iFactory.domain.repositories import StatusRepository
from iFactory.domain.value_objects import EquipmentCode, TimeRange

logger = logging.getLogger(__name__)


class GetDeviceHistoryUseCase:
    """
    Use case: Get device status history over a time range.
    """

    def __init__(self, status_repository: StatusRepository):
        self._status_repo = status_repository

    async def execute(
        self,
        equipment_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[GanttSegmentDTO]:
        try:
            code = EquipmentCode(equipment_code)
            time_range = TimeRange(start=start_time, end=end_time)
            periods = await self._status_repo.get_history(code, time_range)

            from iFactory.application.mappers.status_period_mapper import StatusPeriodMapper

            mapper = StatusPeriodMapper()

            segments = [mapper.to_dto(period, theme="light") for period in periods]

            logger.debug(f"[GetDeviceHistory] Retrieved {len(segments)} segments for {equipment_code}")
            return segments
        except ValueError as e:
            logger.error(f"[GetDeviceHistory] Invalid parameters: {e}")
            return []
        except Exception as e:
            logger.error(f"[GetDeviceHistory] Failed to get history for {equipment_code}: {e}", exc_info=True)
            return []
