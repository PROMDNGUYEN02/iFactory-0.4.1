"""
Infrastructure: Data Mapper.
Translates between Domain Entities and SQLAlchemy Models.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

from .models import DeviceModel, StatusPeriodModel


class OrmDeviceMapper:
    """
    Converts between Device/StatusPeriod aggregates and DB Models.
    Isolates domain types from persistence types.
    """

    # --- Device Entity Mapping ---

    @staticmethod
    def to_entity(model: Optional[DeviceModel]) -> Optional[Device]:
        if model is None:
            return None

        try:
            code_vo = EquipmentCode(model.equip_code)
            try:
                status_vo = MachineStatus(model.equip_status)
            except ValueError:
                status_vo = MachineStatus.UNKNOWN

            return Device(
                equipment_code=code_vo,
                current_status=status_vo,
                last_updated_at=model.last_update,
                name=model.name,
                description=model.description,
            )
        except Exception:
            return None

    @staticmethod
    def to_entities(models: Sequence[DeviceModel]) -> List[Device]:
        result = []
        for model in models:
            entity = OrmDeviceMapper.to_entity(model)
            if entity is not None:
                result.append(entity)
        return result

    @staticmethod
    def to_model(entity: Device) -> DeviceModel:
        return DeviceModel(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_updated_at or datetime.now(),
            is_active=entity.is_active,
            name=entity.name,
            description=entity.description,
        )

    # --- StatusPeriod Value Object Mapping ---

    @staticmethod
    def to_period_entity(model: Optional[StatusPeriodModel]) -> Optional[StatusPeriod]:
        if model is None:
            return None

        try:
            code_vo = EquipmentCode(model.device_id)
            try:
                status_vo = MachineStatus(model.status)
            except ValueError:
                status_vo = MachineStatus.UNKNOWN

            time_range_vo = TimeRange(model.start_time, model.end_time)

            return StatusPeriod(
                equipment_code=code_vo,
                status=status_vo,
                time_range=time_range_vo,
            )
        except Exception:
            return None

    @staticmethod
    def to_period_entities(models: Sequence[StatusPeriodModel]) -> List[StatusPeriod]:
        result = []
        for model in models:
            period = OrmDeviceMapper.to_period_entity(model)
            if period is not None:
                result.append(period)
        return result

    @staticmethod
    def to_period_model(entity: StatusPeriod) -> StatusPeriodModel:
        return StatusPeriodModel(
            id=str(uuid4()),
            device_id=entity.equipment_code.value,
            status=entity.status.value,
            start_time=entity.time_range.start,
            end_time=entity.time_range.end,
        )
