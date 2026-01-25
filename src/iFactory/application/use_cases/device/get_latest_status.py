"""Get latest device status use case."""

import logging
from datetime import timedelta
from typing import Optional

from iFactory.application.config.constants import CacheDefaults, CacheKeys
from iFactory.application.dtos import DeviceStatusDTO
from iFactory.application.interfaces import CacheProvider
from iFactory.application.mappers import DeviceMapper
from iFactory.domain.repositories import DeviceRepository, InputRepository
from iFactory.domain.value_objects import EquipmentCode

logger = logging.getLogger(__name__)


class GetLatestDeviceStatusUseCase:
    """
    Use case: Get latest status for a specific device.
    Query-Only use case.
    """

    __slots__ = ("_device_repo", "_input_repo", "_cache", "_mapper")

    def __init__(
        self,
        device_repository: DeviceRepository,
        input_repository: InputRepository,
        cache_provider: Optional[CacheProvider] = None,
    ):
        self._device_repo = device_repository
        self._input_repo = input_repository
        self._cache = cache_provider
        self._mapper = DeviceMapper()

    async def execute(self, equipment_code: str) -> Optional[DeviceStatusDTO]:
        try:
            code = EquipmentCode(equipment_code)
        except ValueError as e:
            logger.error(f"[GetLatestStatus] Invalid equipment code '{equipment_code}': {e}")
            return self._mapper.create_unknown_dto(equipment_code)

        # Fetch from Domain
        device = await self._device_repo.get_by_code(code)
        if device is None:
            logger.warning(f"[GetLatestStatus] Device '{equipment_code}' not found.")
            return self._mapper.create_unknown_dto(equipment_code)

        # Fetch latest input
        latest_input = await self._input_repo.get_latest(code)

        dto = self._mapper.to_dto(device, latest_input, theme="light")

        return dto
