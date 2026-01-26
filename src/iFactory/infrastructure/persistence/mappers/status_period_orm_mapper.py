"""
Status period ORM mapper - Maps between StatusPeriod entity and StatusHistory model.
"""

from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.value_objects import StatusPeriod
from iFactory.infrastructure.database.models import StatusHistory

__all__ = ["StatusPeriodOrmMapper"]


class StatusPeriodOrmMapper:
    """
    Maps between StatusPeriod domain value object and StatusHistory ORM model.
    Responsibility: ORM Model <-> Domain Value Object.
    """

    @staticmethod
    def to_entity(model: StatusHistory) -> StatusPeriod:
        """Convert ORM model to domain entity."""
        end_time = model.end_time or datetime.now()
        return StatusPeriod.create(code=model.equip_code, raw_status=model.equip_status, start=model.start_time, end=end_time)

    @staticmethod
    def to_entities(models: Sequence[StatusHistory]) -> list[StatusPeriod]:
        """Convert multiple ORM models to domain entities."""
        return [StatusPeriodOrmMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: StatusPeriod) -> StatusHistory:
        """Convert domain entity to ORM model."""
        return StatusHistory(
            equip_code=entity.equipment_code.value,
            equip_status=entity.status.value,
            start_time=entity.time_range.start,
            end_time=entity.time_range.end,
            duration=entity.time_range.duration_seconds,
        )
