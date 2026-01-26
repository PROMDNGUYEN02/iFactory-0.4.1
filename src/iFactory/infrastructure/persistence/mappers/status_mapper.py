from __future__ import annotations
from datetime import datetime
from typing import Sequence
from iFactory.domain.value_objects import EquipmentCode, Status, TimeRange, StatusPeriod
from iFactory.infrastructure.database.models.cold_models import StatusHistory


class StatusPeriodMapper:
    @staticmethod
    def to_entity(model: StatusHistory) -> StatusPeriod:
        end_time = model.end_time or datetime.now()
        return StatusPeriod(
            equipment_code=EquipmentCode(model.equip_code),
            status=Status.normalize(model.equip_status),
            time_range=TimeRange(model.start_time, end_time),
        )

    @staticmethod
    def to_entities(models: Sequence[StatusHistory]) -> list[StatusPeriod]:
        return [StatusPeriodMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: StatusPeriod) -> StatusHistory:
        return StatusHistory(
            equip_code=entity.equipment_code.value,
            equip_status=entity.status.code,
            start_time=entity.time_range.start,
            end_time=entity.time_range.end,
            duration=entity.duration_seconds,
        )
