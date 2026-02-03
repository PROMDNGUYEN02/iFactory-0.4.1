# src/application/queries/device_queries.py
"""
Enhanced Device Queries with Result pattern and caching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from iFactory.shared.core.result import Result, Error, Errors
from iFactory.application.mediator import Request, IRequestHandler
from iFactory.application.common.dtos import DeviceStatusDTO

logger = logging.getLogger(__name__)


# ============================================================================
# Get Device Query
# ============================================================================


@dataclass(frozen=True)
class GetDeviceQuery(Request[Result[DeviceStatusDTO, Error]]):
    """Query to get a single device by code."""

    device_id: str

    @property
    def cache_key(self) -> str:
        return f"device:{self.device_id}"

    cache_ttl: int = 5


class GetDeviceHandler(IRequestHandler[Result[DeviceStatusDTO, Error]]):
    """Handler for GetDeviceQuery."""

    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def handle(
        self,
        request: GetDeviceQuery,
    ) -> Result[DeviceStatusDTO, Error]:
        try:
            async with self._uow_factory() as uow:
                if not uow.devices:
                    return Result.failure(
                        Errors.database(
                            "Device repository not available",
                            operation="get_device",
                        )
                    )

                device = await uow.devices.get_by_code_string(request.device_id)

                if not device:
                    return Result.failure(
                        Errors.not_found(
                            entity="Device",
                            identifier=request.device_id,
                        )
                    )

                dto = DeviceStatusDTO(
                    equip_code=device.equipment_code.value,
                    status_code=str(device.current_status.value),
                    status_name=device.current_status.name,
                    last_update=device.last_updated_at,
                    is_active=device.is_active,
                    name=device.equip_name,
                )

                return Result.success(dto)

        except Exception as e:
            logger.error(f"Failed to get device {request.device_id}: {e}")
            return Result.failure(Errors.database(str(e), operation="get_device"))


# ============================================================================
# Get All Devices Query
# ============================================================================


@dataclass(frozen=True)
class GetAllDevicesQuery(Request[Result[List[DeviceStatusDTO], Error]]):
    """Query to get all devices, optionally filtered by codes."""

    device_ids: Optional[tuple[str, ...]] = None

    @classmethod
    def create(
        cls,
        device_ids: Optional[List[str]] = None,
    ) -> "GetAllDevicesQuery":
        return cls(
            device_ids=tuple(device_ids) if device_ids else None,
        )

    @property
    def cache_key(self) -> str:
        if self.device_ids:
            return f"devices:{hash(self.device_ids)}"
        return "devices:all"

    cache_ttl: int = 3


class GetAllDevicesHandler(IRequestHandler[Result[List[DeviceStatusDTO], Error]]):
    """Handler for GetAllDevicesQuery."""

    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def handle(
        self,
        request: GetAllDevicesQuery,
    ) -> Result[List[DeviceStatusDTO], Error]:
        try:
            async with self._uow_factory() as uow:
                if not uow.devices:
                    return Result.failure(
                        Errors.database(
                            "Device repository not available",
                            operation="get_all_devices",
                        )
                    )

                devices = await uow.devices.get_all()

                dtos = []
                for device in devices:
                    # Filter if device_ids specified
                    if request.device_ids:
                        if device.equipment_code.value not in request.device_ids:
                            continue

                    dto = DeviceStatusDTO(
                        equip_code=device.equipment_code.value,
                        status_code=str(device.current_status.value),
                        status_name=device.current_status.name,
                        last_update=device.last_updated_at,
                        is_active=device.is_active,
                        name=device.equip_name,
                    )
                    dtos.append(dto)

                return Result.success(dtos)

        except Exception as e:
            logger.error(f"Failed to get all devices: {e}")
            return Result.failure(Errors.database(str(e), operation="get_all_devices"))


# ============================================================================
# Get Device Count Query
# ============================================================================


@dataclass(frozen=True)
class GetDeviceCountQuery(Request[Result[int, Error]]):
    """Query to get total device count."""

    @property
    def cache_key(self) -> str:
        return "devices:count"

    cache_ttl: int = 10


class GetDeviceCountHandler(IRequestHandler[Result[int, Error]]):
    """Handler for GetDeviceCountQuery."""

    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def handle(
        self,
        request: GetDeviceCountQuery,
    ) -> Result[int, Error]:
        try:
            async with self._uow_factory() as uow:
                if not uow.devices:
                    return Result.failure(
                        Errors.database(
                            "Device repository not available",
                            operation="count_devices",
                        )
                    )

                devices = await uow.devices.get_all()
                return Result.success(len(devices))

        except Exception as e:
            return Result.failure(Errors.database(str(e), operation="count_devices"))


__all__ = [
    "GetDeviceQuery",
    "GetDeviceHandler",
    "GetAllDevicesQuery",
    "GetAllDevicesHandler",
    "GetDeviceCountQuery",
    "GetDeviceCountHandler",
]
