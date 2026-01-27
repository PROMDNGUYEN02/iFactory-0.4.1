"""
Infrastructure Mapper for Database ORM.
Strictly bi-directional mapping between Domain and Persistence Models.
"""

from __future__ import annotations

from typing import List, Optional, Sequence
from datetime import datetime
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.domain.value_objects.material_batch import MaterialBatch
from iFactory.domain.enums.machine_status import MachineStatus

from .models import (
    DeviceModel,
    StatusPeriodModel,
    MaterialInputHistoryModel,
    LatestMaterialInputModel,
)


class SqlAlchemyMapper:
    """
    Static translator between Domain Objects and SQLAlchemy Models.
    Ensures domain types (Value Objects, Enums) are correctly serialized/deserialized.
    """

    # =========================================================================
    # Device Mapping
    # =========================================================================

    @staticmethod
    def to_device_entity(model: Optional[DeviceModel]) -> Optional[Device]:
        if model is None:
            return None
        try:
            device = Device(
                equipment_code=EquipmentCode(model.equip_code),
                current_status=MachineStatus(model.equip_status),
                last_updated_at=model.last_update,
                name=model.name,
                description=model.description,
            )
            return device
        except Exception:
            return None

    @staticmethod
    def to_device_model(entity: Device) -> DeviceModel:
        return DeviceModel(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_updated_at,
            is_active=entity.is_active,
            name=entity.name,
            description=entity.description,
        )

    # =========================================================================
    # StatusPeriod Mapping
    # =========================================================================

    @staticmethod
    def to_status_period(model: Optional[StatusPeriodModel]) -> Optional[StatusPeriod]:
        if model is None:
            return None
        try:
            return StatusPeriod(
                equipment_code=EquipmentCode(model.device_id),
                status=MachineStatus(model.status),
                time_range=TimeRange(
                    start=model.start_time,
                    end=model.end_time,
                ),
            )
        except Exception:
            return None

    @staticmethod
    def to_status_period_model(period: StatusPeriod) -> StatusPeriodModel:
        # Note: StatusPeriod ValueObject doesn't have ID in domain,
        # but DB needs primary key. We generate one if creating new.
        # This assumes append-only log or that persistence handles ID management if needed.
        return StatusPeriodModel(
            id=str(uuid4()),
            device_id=period.equipment_code.value,
            status=period.status.value,
            start_time=period.time_range.start,
            end_time=period.time_range.end,
        )

    @staticmethod
    def to_status_periods(
        models: Sequence[StatusPeriodModel],
    ) -> List[StatusPeriod]:
        return [p for p in (SqlAlchemyMapper.to_status_period(m) for m in models) if p is not None]

    # =========================================================================
    # MaterialInput Mapping
    # =========================================================================

    @staticmethod
    def to_material_input(
        model: Optional[MaterialInputHistoryModel | LatestMaterialInputModel],
    ) -> Optional[MaterialInput]:
        if model is None:
            return None
        try:
            return MaterialInput(
                equipment_code=EquipmentCode(model.equipment_code),
                material_batch=MaterialBatch(model.material_batch),
                feeding_time=model.feeding_time,
            )
        except Exception:
            return None

    @staticmethod
    def to_material_history_model(
        input_vo: MaterialInput,
    ) -> MaterialInputHistoryModel:
        return MaterialInputHistoryModel(
            id=str(uuid4()),
            equipment_code=input_vo.equipment_code.value,
            material_batch=input_vo.material_batch.value,
            feeding_time=input_vo.feeding_time,
            recorded_at=datetime.now(),
        )

    @staticmethod
    def to_latest_material_model(
        input_vo: MaterialInput,
    ) -> LatestMaterialInputModel:
        return LatestMaterialInputModel(
            id=input_vo.equipment_code.value,
            equipment_code=input_vo.equipment_code.value,
            material_batch=input_vo.material_batch.value,
            feeding_time=input_vo.feeding_time,
        )
