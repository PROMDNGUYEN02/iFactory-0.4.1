# src/iFactory/infrastructure/persistence/sqlalchemy/repositories/device_repository.py
"""
Device Repository - SQLAlchemy implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, TypeVar

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    DeviceModel,
    LatestMaterialInputModel,
    StatusHistoryModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper

logger = logging.getLogger(__name__)

T = TypeVar("T")
DEFAULT_BATCH_SIZE = 100
RUNNING_STATUS = MachineStatus.RUNNING.value


def _chunked(items: List[T], size: int) -> Iterator[List[T]]:
    """Yield successive chunks of specified size."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    SQLAlchemy implementation of DeviceRepository.
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
            return [d for d in (SQLAlchemyMapper.to_device_entity(m) for m in models) if d is not None]
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
            return [d for d in (SQLAlchemyMapper.to_device_entity(m) for m in models) if d is not None]
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
            return [d for d in (SQLAlchemyMapper.to_device_entity(m) for m in models) if d is not None]
        except Exception as e:
            logger.error(f"Error getting active devices: {e}")
            return []

    async def get_by_status(self, status: int) -> Sequence[Device]:
        """Retrieve devices with specific status."""
        try:
            self._stats["queries"] += 1
            stmt = (
                select(DeviceModel)
                .where(
                    DeviceModel.equip_status == status,
                    DeviceModel.is_deleted == False,
                )
                .order_by(DeviceModel.equip_code)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            return [d for d in (SQLAlchemyMapper.to_device_entity(m) for m in models) if d is not None]
        except Exception as e:
            logger.error(f"Error getting devices by status {status}: {e}")
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

            snapshot: List[Tuple[Device, Optional[MaterialInput]]] = []
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

    async def bulk_upsert(self, devices: List[Device]) -> Tuple[int, int]:
        """
        Insert or update multiple devices.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        if not devices:
            return (0, 0)

        inserted = 0
        updated = 0

        try:
            for device in devices:
                # Check if exists
                stmt = select(DeviceModel).where(DeviceModel.equip_code == device.equipment_code.value.upper())
                result = await self._session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    existing.equip_status = device.current_status.value
                    existing.last_update = device.last_updated_at
                    existing.equip_name = device.equip_name
                    existing.reason_code = device.reason_code
                    existing.is_active = device.is_active
                    existing.is_deleted = False
                    updated += 1
                else:
                    # Insert new
                    model = SQLAlchemyMapper.to_device_model(device)
                    self._session.add(model)
                    inserted += 1

                self._stats["saves"] += 1

            logger.debug(f"Bulk upsert: {inserted} inserted, {updated} updated")
            return (inserted, updated)
        except Exception as e:
            logger.error(f"Error in bulk_upsert: {e}")
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

    async def count_by_status(self) -> Dict[int, int]:
        """Count devices grouped by status."""
        try:
            self._stats["queries"] += 1
            stmt = (
                select(
                    DeviceModel.equip_status,
                    func.count(DeviceModel.id).label("count"),
                )
                .where(DeviceModel.is_deleted == False)
                .group_by(DeviceModel.equip_status)
            )
            result = await self._session.execute(stmt)
            rows = result.all()
            return {row.equip_status: row.count for row in rows}
        except Exception as e:
            logger.error(f"Error counting by status: {e}")
            return {}

    def get_stats(self) -> Dict[str, int]:
        """Get repository statistics."""
        return self._stats.copy()

    # ========================================================================
    # Availability Calculation
    # ========================================================================

    async def get_today_run_time(self, code: str) -> float:
        """Get total RUN time (in seconds) for today."""
        try:
            self._stats["queries"] += 1

            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            stmt = select(
                StatusHistoryModel.start_time,
                StatusHistoryModel.end_time,
            ).where(
                and_(
                    StatusHistoryModel.equip_code == code.upper(),
                    StatusHistoryModel.equip_status == RUNNING_STATUS,
                    StatusHistoryModel.start_time < now,
                    ((StatusHistoryModel.end_time > today_start) | (StatusHistoryModel.end_time.is_(None))),
                )
            )

            result = await self._session.execute(stmt)
            rows = result.all()

            total_seconds = 0.0

            for start_time, end_time in rows:
                effective_start = max(start_time, today_start)
                effective_end = end_time if end_time else now
                effective_end = min(effective_end, now)

                if effective_end > effective_start:
                    duration = (effective_end - effective_start).total_seconds()
                    total_seconds += duration

            return total_seconds

        except Exception as e:
            logger.error(f"Error calculating run time for {code}: {e}")
            return 0.0

    async def get_today_run_time_bulk(self, codes: List[str]) -> Dict[str, float]:
        """Get total RUN time for multiple devices."""
        if not codes:
            return {}

        try:
            self._stats["queries"] += 1

            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            upper_codes = [c.upper() for c in codes]

            stmt = (
                select(
                    StatusHistoryModel.equip_code,
                    StatusHistoryModel.start_time,
                    StatusHistoryModel.end_time,
                )
                .where(
                    and_(
                        StatusHistoryModel.equip_code.in_(upper_codes),
                        StatusHistoryModel.equip_status == RUNNING_STATUS,
                        StatusHistoryModel.start_time < now,
                        ((StatusHistoryModel.end_time > today_start) | (StatusHistoryModel.end_time.is_(None))),
                    )
                )
                .order_by(StatusHistoryModel.equip_code)
            )

            result = await self._session.execute(stmt)
            rows = result.all()

            run_times: Dict[str, float] = {code.upper(): 0.0 for code in codes}

            for equip_code, start_time, end_time in rows:
                effective_start = max(start_time, today_start)
                effective_end = min(end_time if end_time else now, now)

                if effective_end > effective_start:
                    duration = (effective_end - effective_start).total_seconds()
                    run_times[equip_code.upper()] += duration

            return run_times

        except Exception as e:
            logger.error(f"Error calculating bulk run times: {e}")
            return {code.upper(): 0.0 for code in codes}


__all__ = ["SqlAlchemyDeviceRepository"]
