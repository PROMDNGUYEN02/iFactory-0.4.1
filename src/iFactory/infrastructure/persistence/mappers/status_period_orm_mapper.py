# File: src/iFactory/infrastructure/persistence/mappers/status_period_orm_mapper.py
"""
Status period ORM mapper - Maps between DeviceHistory entity and StatusHistory model.
"""
from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.value_objects import EquipmentCode, DeviceHistory, Status, TimeRange
from iFactory.infrastructure.database.models import StatusHistory

__all__ = ["StatusPeriodOrmMapper"]


class StatusPeriodOrmMapper:
    """
    Maps between DeviceHistory domain entity and StatusHistory ORM model.
    Responsibility: ORM Model <-> Domain Entity.
    """

    @staticmethod
    def to_entity(model: StatusHistory) -> DeviceHistory:
        """Convert ORM model to domain entity."""
        end_time = model.end_time or datetime.now()
        return DeviceHistory(
            equipment_code=EquipmentCode(model.equip_code),
            status=Status.normalize(model.equip_status),
            time_range=TimeRange(model.start_time, end_time),
        )

    @staticmethod
    def to_entities(models: Sequence[StatusHistory]) -> list[DeviceHistory]:
        """Convert multiple ORM models to domain entities."""
        return [StatusPeriodOrmMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: DeviceHistory) -> StatusHistory:
        """Convert domain entity to ORM model."""
        return StatusHistory(
            equip_code=entity.equipment_code.value,
            equip_status=entity.status.code,
            start_time=entity.start_time,
            end_time=entity.end_time,
            duration=entity.duration_seconds,
        )
