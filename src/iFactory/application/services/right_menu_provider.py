"""
Data providers for Right Menu UI components.
"""

import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.domain.repositories import ProductionRepository
from ...shared.utils.formatters import format_datetime, format_duration, safe_str

__all__ = ["RightMenuDataProvider", "StatusSummaryRow"]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StatusSummaryRow:
    """Summary row for status aggregation (DTO for internal use)."""

    date: str
    equip_code: str
    running: float = 0.0
    shutdown: float = 0.0
    stop: float = 0.0
    maintenance: float = 0.0
    alarm: float = 0.0

    @property
    def total_seconds(self) -> float:
        return self.running + self.shutdown + self.stop + self.maintenance + self.alarm

    @property
    def running_percent(self) -> float:
        total = self.total_seconds
        return self.running / total * 100 if total > 0 else 0.0


class RightMenuDataProvider:
    """
    Provides data for right slide menu.
    Refactored to inject the unified ProductionRepository Interface.
    """

    STATUS_HEADERS = ["Device", "Status", "Start Time", "End Time", "Duration"]
    INPUT_HEADERS = ["Device", "Material Batch", "Feed Time"]

    __slots__ = (
        "_production_repo",
        "_cache",
        "_cache_ttl",
    )

    def __init__(self, production_repository: ProductionRepository, cache_ttl: int = 30):
        self._production_repo = production_repository
        # Type fix: cache stores tuple of (datetime, dict)
        self._cache: Dict[str, Tuple[datetime, Dict]] = {}
        self._cache_ttl = cache_ttl

    def clear_cache(self) -> None:
        self._cache.clear()

    async def get_device_status_history(self, device_code: str, days: int = 7, limit: int = 500) -> Dict[str, Any]:
        """Get status history for a device."""
        cache_key = f"status:{device_code}:{days}"
        if cache_key in self._cache:
            (cached_time, data) = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return data

        try:
            time_range = TimeRange.last_days(days)
            # Call Domain Repository
            records = await self._production_repo.get_status_history(device_code, time_range)

            rows = [
                [
                    safe_str(period.equipment_code.value),
                    safe_str(period.status.name),
                    format_datetime(period.time_range.start),
                    format_datetime(period.time_range.end),
                    format_duration(period.duration_seconds),
                ]
                for period in records[:limit]
            ]
            result = {
                "headers": self.STATUS_HEADERS,
                "rows": rows,
                "total": len(records),
                "status_col": 1,
                "device_code": device_code,
            }
            self._cache[cache_key] = (datetime.now(), result)
            return result
        except Exception as e:
            logger.error(f"Error fetching status for {device_code}: {e}")
            return {
                "headers": self.STATUS_HEADERS,
                "rows": [],
                "total": 0,
                "error": str(e),
            }

    async def get_device_input_history(self, device_code: str, days: int = 7, limit: int = 500) -> Dict[str, Any]:
        """Get input history for a device."""
        cache_key = f"input:{device_code}:{days}"
        if cache_key in self._cache:
            (cached_time, data) = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return data

        try:
            time_range = TimeRange.last_days(days)
            # Call Domain Repository
            records = await self._production_repo.get_input_history(device_code, time_range)

            rows = [
                [
                    safe_str(inp.equipment_code.value),
                    safe_str(inp.material_batch),
                    format_datetime(inp.feeding_time),
                ]
                for inp in records[:limit]
            ]
            result = {
                "headers": self.INPUT_HEADERS,
                "rows": rows,
                "total": len(records),
                "device_code": device_code,
            }
            self._cache[cache_key] = (datetime.now(), result)
            return result
        except Exception as e:
            logger.error(f"Error fetching input for {device_code}: {e}")
            return {
                "headers": self.INPUT_HEADERS,
                "rows": [],
                "total": 0,
                "error": str(e),
            }
