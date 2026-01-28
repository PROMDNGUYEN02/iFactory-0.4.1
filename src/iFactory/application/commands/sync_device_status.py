# """
# Application Command: Sync Single Device Status.
# """

# import logging
# from typing import Optional

# from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
# from iFactory.application.ports.remote_data_source import IRemoteDataSource
# from iFactory.domain.entities.device import Device
# from iFactory.domain.value_objects.equipment_code import EquipmentCode
# from iFactory.domain.enums.machine_status import MachineStatus

# logger = logging.getLogger(__name__)


# class SyncDeviceStatusCommand:
#     """
#     COMMAND: Syncs a single device status by equipment code.
#     Returns: bool (success)
#     """

#     def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
#         self._uow = uow
#         self._remote_api = remote_api

#     async def execute(self, equip_code: str) -> bool:
#         try:
#             raw_data = await self._remote_api.fetch_device_status(equip_code)
#             if not raw_data:
#                 return False

#             # Convert raw status to Enum safely
#             raw_status = raw_data.get("equip_status", "0")
#             try:
#                 status_enum = MachineStatus(int(raw_status))
#             except (ValueError, TypeError):
#                 status_enum = MachineStatus.UNKNOWN

#             # Create Device Entity
#             # Note: Explicitly using constructor to ensure compatibility with recent Domain changes
#             device_entity = Device(
#                 equipment_code=EquipmentCode(raw_data.get("equip_code")),
#                 current_status=status_enum,
#                 last_updated_at=raw_data.get("last_update"),
#             )

#             async with self._uow as uow:
#                 # Use save() which handles upsert via merge
#                 await uow.devices.save(device_entity)
#                 await uow.commit()

#             return True

#         except Exception as e:
#             logger.error(f"Failed to sync device {equip_code}: {e}")
#             return False
