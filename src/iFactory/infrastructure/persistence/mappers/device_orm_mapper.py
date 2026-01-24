# File: src/iFactory/infrastructure/persistence/mappers/device_orm_mapper.py
"""
Device ORM mapper - Maps between Device entity and LatestStatus model.
"""
from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.entities import Device
from iFactory.domain.value_objects import EquipmentCode, Status
from iFactory.infrastructure.database.models import LatestStatus

__all__ = ["DeviceOrmMapper"]


class DeviceOrmMapper:
    """
    Maps between Device domain entity and LatestStatus ORM model.
    Responsibility: ORM Model <-> Domain Entity.
    """

    @staticmethod
    def to_entity(model: LatestStatus) -> Device:
        """Convert ORM model to domain entity."""
        # Use Domain factory/VOs to ensure integrity
        return Device.create(
            code=model.equip_code,
            status=model.equip_status,
            last_update=model.last_update,
        )

    @staticmethod
    def to_entities(models: Sequence[LatestStatus]) -> list[Device]:
        """Convert multiple ORM models to domain entities."""
        return [DeviceOrmMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: Device) -> LatestStatus:
        """Convert domain entity to ORM model."""
        return LatestStatus(
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.code,
            last_update=entity.last_update or datetime.now(),
        )

    @staticmethod
    def update_model(model: LatestStatus, entity: Device) -> LatestStatus:
        """Update existing ORM model from domain entity."""
        model.equip_status = entity.current_status.code
        model.last_update = entity.last_update or datetime.now()
        return model
