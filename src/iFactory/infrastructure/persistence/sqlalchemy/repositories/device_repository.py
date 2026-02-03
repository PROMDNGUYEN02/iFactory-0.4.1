# src/iFactory/infrastructure/persistence/sqlalchemy/repositories/device_repository.py
"""
Device Repository - Compatible with original interface.

Uses simple return types (Optional, Sequence) to match DeviceRepository ABC.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, TypeVar

from sqlalchemy import select, delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    DeviceModel,
    LatestMaterialInputModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper

logger = logging.getLogger(__name__)

T = TypeVar("T")
DEFAULT_BATCH_SIZE = 100


def _chunked(items: List[T], size: int) -> Iterator[List[T]]:
    """Yield successive chunks of specified size."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    SQLAlchemy implementation of DeviceRepository.

    Matches the abstract interface with simple return types.
    """

    def __init__(
        self,
        session: AsyncSession,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._session = session
        self._batch_size = batch_size
        self._stats = {"queries": 0, "saves": 0}

    # ========================================================================
    # Single Entity Operations
    # ========================================================================

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Retrieve a single device by its code."""
        try:
            self._stats["queries"] += 1
            stmt = select(DeviceModel).where(DeviceModel.equip_code == code.value.upper())
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            return SQLAlchemyMapper.to_device_entity(model)
        except Exception as e:
            logger.error(f"Error getting device {code.value}: {e}")
            return None

    async def get_by_code_string(self, code: str) -> Optional[Device]:
        """Get device by code string (convenience method)."""
        try:
            return await self.get_by_code(EquipmentCode(code))
        except Exception as e:
            logger.error(f"Invalid code {code}: {e}")
            return None

    async def save(self, device: Device) -> None:
        """Persist device state."""
        try:
            self._stats["saves"] += 1
            model = SQLAlchemyMapper.to_device_model(device)
            await self._session.merge(model)
        except Exception as e:
            logger.error(f"Error saving device {device.equipment_code}: {e}")
            raise

    async def delete(self, code: EquipmentCode) -> bool:
        """Remove a device."""
        try:
            stmt = delete(DeviceModel).where(DeviceModel.equip_code == code.value)
            result = await self._session.execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting device {code.value}: {e}")
            return False

    async def exists(self, code: EquipmentCode) -> bool:
        """Check if device exists."""
        try:
            stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.equip_code == code.value)
            result = await self._session.execute(stmt)
            return result.scalar_one() > 0
        except Exception as e:
            logger.error(f"Error checking existence for {code.value}: {e}")
            return False

    # ========================================================================
    # Bulk Read Operations
    # ========================================================================

    async def get_all(self) -> Sequence[Device]:
        """Retrieve all registered devices."""
        try:
            self._stats["queries"] += 1
            stmt = select(DeviceModel).where(DeviceModel.is_deleted == False).order_by(DeviceModel.equip_code)
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            return [SQLAlchemyMapper.to_device_entity(m) for m in models if m is not None]
        except Exception as e:
            logger.error(f"Error getting all devices: {e}")
            return []

    async def get_all_as_dict(self) -> Dict[str, Device]:
        """Retrieve all devices as dictionary keyed by uppercase code."""
        devices = await self.get_all()
        return {device.equipment_code.value.upper(): device for device in devices if device is not None}

    async def get_by_codes(self, codes: List[str]) -> Sequence[Device]:
        """Retrieve multiple devices by their codes."""
        if not codes:
            return []

        try:
            self._stats["queries"] += 1
            upper_codes = [c.upper() for c in codes]
            stmt = select(DeviceModel).where(DeviceModel.equip_code.in_(upper_codes)).order_by(DeviceModel.equip_code)
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            return [SQLAlchemyMapper.to_device_entity(m) for m in models if m is not None]
        except Exception as e:
            logger.error(f"Error getting devices by codes: {e}")
            return []

    async def get_by_codes_as_dict(self, codes: List[str]) -> Dict[str, Device]:
        """Retrieve multiple devices as dictionary."""
        devices = await self.get_by_codes(codes)
        return {device.equipment_code.value.upper(): device for device in devices if device is not None}

    async def get_active(self) -> Sequence[Device]:
        """Retrieve only active devices."""
        try:
            self._stats["queries"] += 1
            stmt = (
                select(DeviceModel)
                .where(
                    DeviceModel.is_active == True,
                    DeviceModel.is_deleted == False,
                )
                .order_by(DeviceModel.equip_code)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            return [SQLAlchemyMapper.to_device_entity(m) for m in models if m is not None]
        except Exception as e:
            logger.error(f"Error getting active devices: {e}")
            return []

    async def get_dashboard_snapshot(
        self,
    ) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """Get devices with latest material input for dashboard."""
        try:
            self._stats["queries"] += 1
            stmt = (
                select(DeviceModel, LatestMaterialInputModel)
                .outerjoin(
                    LatestMaterialInputModel,
                    DeviceModel.equip_code == LatestMaterialInputModel.equipment_code,
                )
                .where(DeviceModel.is_deleted == False)
                .order_by(DeviceModel.equip_code)
            )
            result = await self._session.execute(stmt)
            rows = result.all()

            snapshot = []
            for dev_model, input_model in rows:
                if not dev_model:
                    continue
                device = SQLAlchemyMapper.to_device_entity(dev_model)
                material = SQLAlchemyMapper.to_material_input(input_model) if input_model else None
                if device:
                    snapshot.append((device, material))

            return snapshot
        except Exception as e:
            logger.error(f"Error getting dashboard snapshot: {e}")
            return []

    # ========================================================================
    # Bulk Write Operations
    # ========================================================================

    async def bulk_save(self, devices: List[Device]) -> None:
        """Persist multiple devices in batch."""
        if not devices:
            return

        try:
            total = len(devices)
            saved = 0

            for chunk in _chunked(devices, self._batch_size):
                for device in chunk:
                    model = SQLAlchemyMapper.to_device_model(device)
                    await self._session.merge(model)
                    self._stats["saves"] += 1
                saved += len(chunk)

                if saved < total:
                    await self._session.flush()

            logger.debug(f"Bulk saved {total} devices")
        except Exception as e:
            logger.error(f"Error bulk saving devices: {e}")
            raise

    # ========================================================================
    # Statistics
    # ========================================================================

    async def count(self) -> int:
        """Count total devices."""
        try:
            stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.is_deleted == False)
            result = await self._session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting devices: {e}")
            return 0

    def get_stats(self) -> Dict[str, int]:
        """Get repository statistics."""
        return self._stats.copy()


__all__ = ["SqlAlchemyDeviceRepository"]
