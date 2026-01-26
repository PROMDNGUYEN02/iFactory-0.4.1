"""
Status mapping utilities and entity-to-DTO mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from iFactory.application.dtos import GanttSegmentDTO
from iFactory.application.services.status_ui_mapper import StatusUIMapper

if TYPE_CHECKING:
    from iFactory.domain.value_objects import StatusPeriod

__all__ = [
    "StatusPeriodMapper",
]


_default_mapper_instance = None


def _get_default_mapper() -> "StatusPeriodMapper":
    """Get default singleton instance for static methods."""
    global _default_mapper_instance
    if _default_mapper_instance is None:
        _default_mapper_instance = StatusPeriodMapper()
    return _default_mapper_instance


# --- Entity Mapper ---
class StatusPeriodMapper:
    """Maps StatusPeriod domain value object to GanttSegmentDTO."""

    __slots__ = ("_ui_mapper",)

    def __init__(self, ui_mapper: StatusUIMapper = None) -> None:
        self._ui_mapper = ui_mapper or StatusUIMapper()

    def to_dto(self, entity: "StatusPeriod", theme: str = "light") -> GanttSegmentDTO:
        """Convert a StatusPeriod entity to a GanttSegmentDTO."""
        return GanttSegmentDTO(
            start_time=entity.time_range.start,
            end_time=entity.time_range.end,
            status_code=entity.status.value,
            status_name=entity.status.name,
            status_color=self._ui_mapper.get_color(entity.status.value, theme),
        )

    @staticmethod
    def to_dto(entity: "StatusPeriod", theme: str = "light") -> GanttSegmentDTO:
        """Static method for backward compatibility. Uses default mapper instance."""
        return _get_default_mapper().to_dto(entity, theme)
