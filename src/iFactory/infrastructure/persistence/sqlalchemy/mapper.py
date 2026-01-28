"""
Infrastructure: SQLAlchemy Data Mappers.
Translates between Domain Entities/VOs and Persistence Models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

from .models import DeviceModel, StatusPeriodModel, MaterialInputHistoryModel, LatestMaterialInputModel


class SQLAlchemyMapper:
    """
    Pure transformation layer between Domain and SQLAlchemy.
    """

    # --- Device Mapping ---

    @staticmethod
    def to_device_entity(model: Optional[DeviceModel]) -> Optional[Device]:
        if not model:
            return None

        try:
            status = MachineStatus(model.equip_status)
        except ValueError:
            status = MachineStatus.UNKNOWN

        return Device(
            equipment_code=EquipmentCode(model.equip_code),
            current_status=status,
            last_updated_at=model.last_update,
            name=model.name,
            description=model.description,
        )

    @staticmethod
    def to_device_model(entity: Device) -> DeviceModel:
        return DeviceModel(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_updated_at or datetime.now(),
            is_active=getattr(entity, "is_active", True),
            name=entity.name,
            description=entity.description,
        )

    # --- Status Period Mapping ---

    @staticmethod
    def to_status_period(model: Optional[StatusPeriodModel]) -> Optional[StatusPeriod]:
        if not model:
            return None

        try:
            status = MachineStatus(model.status)
        except ValueError:
            status = MachineStatus.UNKNOWN

        return StatusPeriod(equipment_code=EquipmentCode(model.device_id), status=status, time_range=TimeRange(model.start_time, model.end_time))

    @staticmethod
    def to_status_period_model(vo: StatusPeriod) -> StatusPeriodModel:
        return StatusPeriodModel(
            id=str(uuid4()), device_id=vo.equipment_code.value, status=vo.status.value, start_time=vo.time_range.start, end_time=vo.time_range.end
        )

    # --- Material Input Mapping ---

    @staticmethod
    def to_material_input(model: MaterialInputHistoryModel | LatestMaterialInputModel | None) -> Optional[MaterialInput]:
        if not model:
            return None

        return MaterialInput(code=EquipmentCode(model.equipment_code), batch_id=model.material_batch, timestamp=model.feeding_time)

    @staticmethod
    def to_material_history_model(vo: MaterialInput) -> MaterialInputHistoryModel:
        return MaterialInputHistoryModel(
            id=str(uuid4()), equipment_code=vo.code.value, material_batch=vo.batch_id, feeding_time=vo.timestamp, recorded_at=datetime.now()
        )

    @staticmethod
    def to_latest_material_model(vo: MaterialInput) -> LatestMaterialInputModel:
        return LatestMaterialInputModel(id=str(uuid4()), equipment_code=vo.code.value, material_batch=vo.batch_id, feeding_time=vo.timestamp)


# Compatibility Alias for code expecting the old name
OrmDeviceMapper = SQLAlchemyMapper
