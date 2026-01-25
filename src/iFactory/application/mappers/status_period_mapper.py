"""
Status mapping utilities and entity-to-DTO mapping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from iFactory.application.dtos import GanttSegmentDTO
from iFactory.application.services.status_ui_mapper import StatusUIMapper

if TYPE_CHECKING:
    from iFactory.domain import DeviceHistory

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
    """Maps DeviceHistory domain entity to GanttSegmentDTO."""

    __slots__ = ("_ui_mapper",)

    def __init__(self, ui_mapper: StatusUIMapper = None) -> None:
        """
        Initialize mapper with UI mapper.

        Args:
            ui_mapper: StatusUIMapper for UI data mapping. Defaults to StatusUIMapper.
        """
        self._ui_mapper = ui_mapper or StatusUIMapper()

    def to_dto(self, entity: "DeviceHistory", theme: str = "light") -> GanttSegmentDTO:
        """Convert a DeviceHistory entity to a GanttSegmentDTO."""
        return GanttSegmentDTO(
            start_time=entity.start_time,
            end_time=entity.end_time,
            status_code=entity.status_code,
            status_name=entity.status_name,
            status_color=self._ui_mapper.get_color(entity.status_code, theme),
        )

    @staticmethod
    def to_dto(entity: "DeviceHistory", theme: str = "light") -> GanttSegmentDTO:
        """Static method for backward compatibility. Uses default mapper instance."""
        return _get_default_mapper().to_dto(entity, theme)
