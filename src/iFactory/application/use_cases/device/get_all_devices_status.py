"""Get all devices status use case."""

import logging
from datetime import timedelta
from typing import Optional

from iFactory.application.config.constants import CacheDefaults, CacheKeys
from iFactory.application.dto import DeviceStatusDTO
from iFactory.application.interfaces import CacheProvider
from iFactory.application.mappers import DeviceMapper
from iFactory.domain.repositories import DeviceRepository

logger = logging.getLogger(__name__)


class GetAllDevicesStatusUseCase:
    """
    Use case: Get latest status for all or specified devices.
    """

    def __init__(self, device_repository: DeviceRepository, cache_provider: Optional[CacheProvider] = None):
        self._device_repo = device_repository
        self._cache = cache_provider

    async def execute(self, equipment_codes: Optional[list[str]] = None) -> dict[str, DeviceStatusDTO]:
        try:
            if equipment_codes:
                from iFactory.domain.value_objects import EquipmentCode
                codes_vo = [EquipmentCode(c) for c in equipment_codes]
                devices = await self._device_repo.get_by_codes(codes_vo)
            else:
                devices = await self._device_repo.get_all()

            result: dict[str, DeviceStatusDTO] = {}
            mapper = DeviceMapper()

            for device in devices:
                code = str(device.equipment_code)
                dto = mapper.to_dto(device, latest_input=None, theme="light")
                result[code] = dto

                if self._cache:
                    try:
                        cache_key = CacheKeys.device_status(code)
                        await self._cache.set(
                            cache_key,
                            dto.to_dict(),
                            ttl=timedelta(seconds=CacheDefaults.TTL_STATUS),
                        )
                    except Exception:
                        pass

            logger.info(f"[GetAllDevices] Retrieved statuses for {len(result)} devices.")
            return result
        except Exception as e:
            logger.error(f"[GetAllDevices] Failed to retrieve devices: {e}", exc_info=True)
            return {}
