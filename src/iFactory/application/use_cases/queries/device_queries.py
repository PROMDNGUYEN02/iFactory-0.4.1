from typing import List, Optional

from iFactory.application.dto.device_dto import DeviceDTO, DeviceSummaryDTO
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode


class DeviceQueries:
    """
    Read-only use cases for Device data.
    """

    def __init__(self, uow: AbstractUnitOfWork):
        self._uow = uow

    async def get_all_summaries(self) -> List[DeviceSummaryDTO]:
        """
        Returns a list of device summaries for dashboards.
        """
        async with self._uow as uow:
            devices = await uow.devices.get_all()
            return [self._map_to_summary(d) for d in devices]

    async def get_details(self, code: str) -> Optional[DeviceDTO]:
        """
        Returns full details for a specific device.
        """
        async with self._uow as uow:
            try:
                e_code = EquipmentCode(code)
                device = await uow.devices.get_by_code(e_code)
                if not device:
                    return None
                return self._map_to_dto(device)
            except Exception:
                return None

    def _map_to_summary(self, device: Device) -> DeviceSummaryDTO:
        return DeviceSummaryDTO(
            equipment_code=device.equipment_code.value,
            status_code=device.current_status.value,
            status_name=device.current_status.name,
            last_updated=device.last_updated_at,
        )

    def _map_to_dto(self, device: Device) -> DeviceDTO:
        return DeviceDTO(
            equipment_code=device.equipment_code.value,
            status_code=device.current_status.value,
            status_name=device.current_status.name,
            is_active=device.is_active,
            last_updated=device.last_updated_at,
            name=device.name,
            description=device.description,
        )
