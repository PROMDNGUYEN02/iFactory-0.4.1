from typing import List
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.domain.entities.device import Device
from iFactory.application.exceptions import ResourceNotFoundException


class GetDeviceHistoryUseCase:
    """Use case to fetch historical data of a device."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, equip_code: str) -> List[Device]:
        async with self._uow:
            device = await self._uow.devices.get_by_equipment_code(equip_code)
            if not device:
                raise ResourceNotFoundException("Device", equip_code)

            # Giả định repository có hàm get_history
            history = await self._uow.devices.get_history(equip_code)
            return history
