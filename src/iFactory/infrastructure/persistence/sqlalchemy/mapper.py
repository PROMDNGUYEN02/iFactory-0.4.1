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
from iFactory.domain.value_objects.material_batch import MaterialBatch
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

from .models import DeviceModel, StatusHistoryModel, MaterialInputHistoryModel, LatestMaterialInputModel


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
            equip_name=model.equip_name,
            reason_code=model.reason_code,
        )

    @staticmethod
    def to_device_model(entity: Device) -> DeviceModel:
        return DeviceModel(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_updated_at or datetime.now(),
            equip_name=entity.equip_name,
            reason_code=entity.reason_code,
            is_active=getattr(entity, "is_active", True),
        )

    # --- Status Period Mapping (FIXED) ---
    @staticmethod
    def to_status_period(model: Optional[StatusHistoryModel]) -> Optional[StatusPeriod]:
        if not model:
            return None

        try:
            status = MachineStatus(model.equip_status)
        except ValueError:
            status = MachineStatus.UNKNOWN

        # LOGIC: Nếu end_time is null thì chèn now
        # FIX: Kẹp (Clamp) giá trị now để đảm bảo không nhỏ hơn start_time
        if model.end_time:
            effective_end = model.end_time
        else:
            now = datetime.now()
            # Nếu start_time ở tương lai (do lệch giờ), ép end_time = start_time để tránh lỗi
            effective_end = max(model.start_time, now)

        return StatusPeriod(equipment_code=EquipmentCode(model.equip_code), status=status, time_range=TimeRange(model.start_time, effective_end))

    @staticmethod
    def to_status_period_model(vo: StatusPeriod, equip_name: Optional[str] = None) -> StatusHistoryModel:
        """
        FIXED: Added equip_name to arguments to persist name in history table.
        """
        return StatusHistoryModel(
            id=str(uuid4()),
            equip_code=vo.equipment_code.value,
            equip_name=equip_name,  # --- Added Name ---
            equip_status=vo.status.value,
            start_time=vo.time_range.start,
            end_time=vo.time_range.end,
        )

    # --- Material Input Mapping ---

    @staticmethod
    def to_material_input(model: MaterialInputHistoryModel | LatestMaterialInputModel | None) -> Optional[MaterialInput]:
        if not model:
            return None

        return MaterialInput(
            equipment_code=EquipmentCode(model.equipment_code), material_batch=MaterialBatch(model.material_batch), feeding_time=model.feeding_time
        )

    @staticmethod
    def to_material_history_model(vo: MaterialInput) -> MaterialInputHistoryModel:
        return MaterialInputHistoryModel(
            id=str(uuid4()), equipment_code=vo.code.value, material_batch=vo.batch_id, feeding_time=vo.timestamp, recorded_at=datetime.now()
        )

    @staticmethod
    def to_latest_material_model(vo: MaterialInput) -> LatestMaterialInputModel:
        return LatestMaterialInputModel(id=str(uuid4()), equipment_code=vo.code.value, material_batch=vo.batch_id, feeding_time=vo.timestamp)


# Compatibility Alias
OrmDeviceMapper = SQLAlchemyMapper
