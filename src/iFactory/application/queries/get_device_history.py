from typing import List
from iFactory.application.dto.device_dto import DeviceHistoryDTO
from iFactory.application.ports.unit_of_work import IUnitOfWork
from iFactory.application.exceptions.application_exceptions import ResourceNotFoundException


class GetDeviceHistoryQuery:
    """
    QUERY: Fetches historical states of a single device.
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, equip_code: str) -> List[DeviceHistoryDTO]:
        async with self._uow as uow:
            device = await uow.devices.get_by_equipment_code(equip_code)
            if not device:
                raise ResourceNotFoundException(f"Device not found: {equip_code}")

            history_entities = await uow.devices.get_history(equip_code)

            return [DeviceHistoryDTO(equip_code=h.code, status_code=h.status, timestamp=h.last_update) for h in history_entities]
