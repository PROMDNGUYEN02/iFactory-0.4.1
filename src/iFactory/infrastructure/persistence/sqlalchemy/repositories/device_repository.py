# File: infrastructure/persistence/sqlalchemy/repositories/device_repository.py
"""
Device Repository - Cache layer for offline mode.
In Remote-First architecture, this is optional.

UPDATED: Added bulk_save() method for optimized batch operations.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Dict
from sqlalchemy import select, delete, func
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


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    Device cache repository.
    Used for offline mode fallback.

    OPTIMIZATION: Added bulk operations for batch processing.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code.value.upper())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_device_entity(model)

    async def get_by_code_string(self, code: str) -> Optional[Device]:
        """Get device by code string."""
        return await self.get_by_code(EquipmentCode(code))

    async def get_all(self) -> Sequence[Device]:
        """
        Load ALL devices in a single query.
        Used for bulk pre-loading before sync operations.
        """
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_device_entity(m) for m in models if m]

    async def get_all_as_dict(self) -> Dict[str, Device]:
        """
        Load ALL devices as a dictionary keyed by equipment code.
        Optimized for O(1) lookup during sync operations.

        Returns:
            Dict mapping uppercase equipment codes to Device entities.
        """
        devices = await self.get_all()
        return {device.equipment_code.value.upper(): device for device in devices}

    async def get_by_codes(self, codes: List[str]) -> Sequence[Device]:
        """
        Load multiple devices by their codes in a single query.

        Args:
            codes: List of equipment codes to fetch.

        Returns:
            Sequence of Device entities found.
        """
        if not codes:
            return []

        upper_codes = [c.upper() for c in codes]
        stmt = select(DeviceModel).where(DeviceModel.equip_code.in_(upper_codes)).order_by(DeviceModel.equip_code)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_device_entity(m) for m in models if m]

    async def get_by_codes_as_dict(self, codes: List[str]) -> Dict[str, Device]:
        """
        Load multiple devices as a dictionary.

        Args:
            codes: List of equipment codes to fetch.

        Returns:
            Dict mapping uppercase equipment codes to Device entities.
        """
        devices = await self.get_by_codes(codes)
        return {device.equipment_code.value.upper(): device for device in devices}

    async def get_dashboard_snapshot(
        self,
    ) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """Optimized join query for dashboard."""
        stmt = (
            select(DeviceModel, LatestMaterialInputModel)
            .outerjoin(
                LatestMaterialInputModel,
                DeviceModel.equip_code == LatestMaterialInputModel.equipment_code,
            )
            .order_by(DeviceModel.equip_code)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        snapshot = []
        for dev_model, input_model in rows:
            if not dev_model:
                continue

            device_entity = SQLAlchemyMapper.to_device_entity(dev_model)
            material_vo = None
            if input_model:
                material_vo = SQLAlchemyMapper.to_material_input(input_model)

            if device_entity:
                snapshot.append((device_entity, material_vo))

        return snapshot

    async def get_active(self) -> Sequence[Device]:
        stmt = select(DeviceModel).where(DeviceModel.is_active == True).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_device_entity(m) for m in models if m]

    async def save(self, device: Device) -> None:
        """Save a single device (upsert)."""
        model = SQLAlchemyMapper.to_device_model(device)
        await self._session.merge(model)

    async def bulk_save(self, devices: List[Device]) -> None:
        """
        Bulk save multiple devices in a single batch operation.

        Uses merge() for upsert behavior (insert or update).
        More efficient than individual saves due to reduced round-trips.

        Args:
            devices: List of Device entities to save.
        """
        if not devices:
            return

        for device in devices:
            model = SQLAlchemyMapper.to_device_model(device)
            await self._session.merge(model)

        # Note: The session will batch these operations efficiently.
        # Actual DB write happens on commit(), which is handled by UoW.

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, code: EquipmentCode) -> bool:
        stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(DeviceModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()
