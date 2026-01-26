"""
Provides aggregated summary data.
"""

import logging
from typing import List, Dict

from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.repositories import ProductionRepository

from .right_menu_provider import StatusSummaryRow

__all__ = ["SummaryDataProvider"]

logger = logging.getLogger(__name__)


class SummaryDataProvider:
    """
    Provides aggregated summary data.
    """

    __slots__ = ("_production_repo",)

    def __init__(self, production_repository: ProductionRepository):
        self._production_repo = production_repository

    async def get_summary(self, device_codes: List[str], days: int = 7) -> List[StatusSummaryRow]:
        """Get aggregated summary for devices."""
        if not device_codes:
            return []
        summaries: Dict[str, StatusSummaryRow] = {}
        time_range = TimeRange.last_days(days)

        def _normalize_status(status_name: str) -> str:
            if not status_name:
                return "unknown"
            return str(status_name).strip().lower()

        try:
            for code_str in device_codes:
                # Convert string to Domain Value Object
                code = EquipmentCode(code_str)

                # Call Domain Repository
                records = await self._production_repo.get_status_history(code, time_range)
                for period in records:
                    # Access the new TimeRange value object for the start time
                    date_str = period.time_range.start.strftime("%Y-%m-%d")
                    key = f"{date_str}|{code_str}"
                    if key not in summaries:
                        summaries[key] = StatusSummaryRow(date=date_str, equip_code=code_str)
                    row = summaries[key]

                    # Access the new Status value object for the name
                    duration = period.duration_seconds
                    status_name = _normalize_status(period.status.name)

                    if status_name == "running":
                        row.running += duration
                    elif status_name == "shutdown":
                        row.shutdown += duration
                    # Handle both 'stop' and the domain-canonical 'stopped'
                    elif status_name == "stopped" or status_name == "stop":
                        row.stop += duration
                    elif status_name == "maintenance":
                        row.maintenance += duration
                    elif status_name == "alarm":
                        row.alarm += duration
            return sorted(summaries.values(), key=lambda r: (r.date, r.equip_code), reverse=True)
        except Exception as e:
            logger.error(f"Summary error: {e}", exc_info=True)
            return []
