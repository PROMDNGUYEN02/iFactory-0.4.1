"""
Generate Production Timeline Query.
"""

from datetime import datetime
from typing import List, Callable, Any

from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.cache import ICacheProvider


class GenerateProductionTimelineQuery:
    """
    QUERY: Fetches production history for a device and formats it as a timeline.
    Read-only, no domain mutation.
    """

    def __init__(self, unit_of_work_factory: Callable[[], AbstractUnitOfWork], cache_provider: ICacheProvider):
        self._uow_factory = unit_of_work_factory
        self._cache = cache_provider

    async def execute(self, equip_code: str, start_time: datetime, end_time: datetime, fill_gaps: bool = True) -> List[dict]:
        """
        Executes the timeline generation query.
        """
        async with self._uow_factory() as uow:
            # Lấy lịch sử thực tế từ DB (bảng status_periods)
            history = await uow.devices.get_history(equip_code, start_time, end_time)

        segments = []
        for h in history:
            # Xử lý kỳ đang mở (chưa kết thúc) -> end_time = thời gian kết thúc của biểu đồ (hoặc now)
            segment_end = h.end_time if h.end_time else end_time

            # Cắt bớt nếu segment vượt quá phạm vi chart để hiển thị đúng khung nhìn
            valid_start = max(h.start_time, start_time)
            valid_end = min(segment_end, end_time)

            if valid_start < valid_end:
                segments.append(
                    {
                        "equip_code": h.device_code,
                        "status_code": h.status_code,
                        # Nếu có mapping status name, có thể map ở đây hoặc ở Presenter
                        "status_name": h.status_code,
                        "start_time": valid_start,
                        "end_time": valid_end,
                    }
                )

        return segments
