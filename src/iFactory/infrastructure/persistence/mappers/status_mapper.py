from __future__ import annotations
from datetime import datetime
from typing import Sequence

# FIXED: Separated MachineStatus import to its new location
from iFactory.domain.value_objects import EquipmentCode, TimeRange, StatusPeriod
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.infrastructure.database.models.cold_models import StatusHistoryModel


class StatusPeriodMapper:
    @staticmethod
    def to_entity(model: StatusHistoryModel) -> StatusPeriod:
        end_time = model.end_time or datetime.now()
        return StatusPeriod(
            equipment_code=EquipmentCode(model.equip_code),
            status=MachineStatus.from_business_term(model.equip_status),
            time_range=TimeRange(model.start_time, end_time),
        )

    @staticmethod
    def to_entities(models: Sequence[StatusHistoryModel]) -> list[StatusPeriod]:
        return [StatusPeriodMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: StatusPeriod) -> StatusHistoryModel:
        return StatusHistoryModel(
            equip_code=entity.equipment_code.value,
            equip_status=entity.status.value,
            start_time=entity.time_range.start,
            end_time=entity.time_range.end,
            duration=entity.time_range.duration_seconds,
        )
