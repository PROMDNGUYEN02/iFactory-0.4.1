"""
Provides aggregated summary data.
"""

import logging
from typing import List, Dict

from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.domain.repositories import StatusRepository

from .right_menu_provider import StatusSummaryRow

__all__ = ["SummaryDataProvider"]

logger = logging.getLogger(__name__)


class SummaryDataProvider:
    """
    Provides aggregated summary data.
    """

    __slots__ = ("_status_repo",)

    def __init__(self, status_repository: StatusRepository):
        self._status_repo = status_repository

    async def get_summary(self, device_codes: List[str], days: int = 7) -> List[StatusSummaryRow]:
        """Get aggregated summary for devices."""
        if not device_codes:
            return []
        summaries: Dict[str, StatusSummaryRow] = {}
        time_range = TimeRange.last_days(days)

        def _normalize_status(status_name: str) -> str:
            # Should ideally use StatusMapper utility, but keeping simple here to avoid circular import if mapper is in application/mappers
            # Ideally import from application.mappers.status_period_mapper import StatusMapper
            if not status_name:
                return "unknown"
            return str(status_name).strip().lower()

        try:
            for code in device_codes:
                records = await self._status_repo.get_history(code, time_range)
                for period in records:
                    date_str = period.start_time.strftime("%Y-%m-%d")
                    key = f"{date_str}|{code}"
                    if key not in summaries:
                        summaries[key] = StatusSummaryRow(date=date_str, equip_code=code)
                    row = summaries[key]
                    duration = period.duration_seconds
                    status_name = _normalize_status(str(period.status_name))  # Assuming status_name is available

                    if status_name == "running":
                        row.running += duration
                    elif status_name == "shutdown":
                        row.shutdown += duration
                    elif status_name == "stop":
                        row.stop += duration
                    elif status_name == "maintenance":
                        row.maintenance += duration
                    elif status_name == "alarm":
                        row.alarm += duration
            return sorted(summaries.values(), key=lambda r: (r.date, r.equip_code), reverse=True)
        except Exception as e:
            logger.error(f"Summary error: {e}", exc_info=True)
            return []
