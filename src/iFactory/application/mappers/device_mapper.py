"""
Device entity -> DTO mapper.
Strict Clean Architecture: Pure data mapping, NO UI logic (no themes, no colors).
"""

from typing import TYPE_CHECKING, Optional

from iFactory.application.dtos.device_dtos import DeviceStatusDTO

if TYPE_CHECKING:
    from iFactory.domain.entities.device import Device
    from iFactory.domain.value_objects.material_input import MaterialInput


def to_device_status_dto(
    device: "Device",
    latest_input: Optional["MaterialInput"] = None,
) -> DeviceStatusDTO:
    """
    Pure function to convert a Device Domain Entity to a DeviceStatusDTO.
    UI-specific mapping (colors, display text) occurs in the Presentation layer.
    """
    material_batch = None
    feeding_time = None

    if latest_input:
        material_batch = latest_input.material_batch
        feeding_time = latest_input.feeding_time

    return DeviceStatusDTO(
        equip_code=str(device.equipment_code),
        status_code=device.current_status.code if device.current_status else "0",
        status_name=device.current_status.name if device.current_status else "unknown",
        last_update=device.updated_at,
        material_batch=material_batch,
        feeding_time=feeding_time,
        is_active=device.is_active,
    )


def create_unknown_device_dto(equip_code: str) -> DeviceStatusDTO:
    """Create a DTO representing an unknown device state."""
    return DeviceStatusDTO(
        equip_code=equip_code, status_code="0", status_name="unknown", last_update=None, material_batch=None, feeding_time=None, is_active=False
    )
