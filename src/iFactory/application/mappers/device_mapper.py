"""
Device entity -> DTO mapper.
"""

from typing import TYPE_CHECKING, Optional

from iFactory.application.dtos import DeviceStatusDTO
from iFactory.application.services.status_ui_mapper import StatusUIMapper

if TYPE_CHECKING:
    from iFactory.domain.entities import Device
    from iFactory.domain import MaterialInput

__all__ = ["DeviceMapper"]


_default_mapper_instance = None


def get_default_mapper() -> "DeviceMapper":
    """Get default singleton instance for static methods."""
    global _default_mapper_instance
    if _default_mapper_instance is None:
        _default_mapper_instance = DeviceMapper()
    return _default_mapper_instance


class DeviceMapper:
    """Maps Device domain entity to DeviceStatusDTO."""

    __slots__ = ("_ui_mapper",)

    def __init__(self, ui_mapper: Optional[StatusUIMapper] = None) -> None:
        """
        Initialize mapper with UI mapper.

        Args:
            ui_mapper: StatusUIMapper for UI data mapping. Defaults to StatusUIMapper.
        """
        self._ui_mapper = ui_mapper or StatusUIMapper()

    def to_dto(
        self,
        device: "Device",
        latest_input: Optional["MaterialInput"] = None,
        theme: str = "light",
    ) -> DeviceStatusDTO:
        """Convert a Device entity to a DeviceStatusDTO."""
        status_code = device.current_status.code

        material_batch = None
        feeding_time = None
        if latest_input:
            material_batch = latest_input.material_batch
            feeding_time = latest_input.feeding_time

        return DeviceStatusDTO(
            equip_code=str(device.equipment_code),
            status_code=status_code,
            status_name=device.current_status.name,
            status_display=self._ui_mapper.get_display_text(status_code),
            status_color=self._ui_mapper.get_color(status_code, theme),
            last_update=device.last_update,
            material_batch=material_batch,
            feeding_time=feeding_time,
        )

    def create_unknown_dto(self, equip_code: str, theme: str = "light") -> DeviceStatusDTO:
        """Create a DTO representing an unknown device state."""
        status_code = "0"
        return DeviceStatusDTO(
            equip_code=equip_code,
            status_code=status_code,
            status_name="unknown",
            status_display=self._ui_mapper.get_display_text(status_code),
            status_color=self._ui_mapper.get_color(status_code, theme),
        )
