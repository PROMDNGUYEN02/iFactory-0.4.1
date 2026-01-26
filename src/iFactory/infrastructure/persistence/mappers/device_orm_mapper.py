"""
Device ORM mapper - Maps between Device entity and LatestStatus model.
"""

from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.entities import Device
from iFactory.domain.value_objects import EquipmentCode
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.infrastructure.database.models.hot_models import LatestStatus

__all__ = ["DeviceOrmMapper"]


class DeviceOrmMapper:
    """
    Maps between Device domain entity and LatestStatus ORM model.
    Responsibility: ORM Model <-> Domain Entity.
    """

    @staticmethod
    def to_entity(model: LatestStatus) -> Device:
        """Convert ORM model to domain entity."""
        return Device.create(
            code=model.equip_code,
            raw_status=model.equip_status,
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
            equip_status=entity.current_status.value,
            last_update=entity.last_update or datetime.now(),
        )

    @staticmethod
    def update_model(model: LatestStatus, entity: Device) -> LatestStatus:
        """Update existing ORM model from domain entity."""
        model.equip_status = entity.current_status.value
        model.last_update = entity.last_update or datetime.now()
        return model
