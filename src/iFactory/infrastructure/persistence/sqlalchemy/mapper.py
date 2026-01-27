"""
Infrastructure Mapper for Database ORM.
Strictly bi-directional static mapping between Domain and Persistence.
No side effects, no database queries.
"""

from __future__ import annotations
from datetime import datetime
from typing import Sequence, List, Optional
import uuid

from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod

from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceModel, StatusPeriodModel


class OrmDeviceMapper:
    """Translates between Domain Aggregates and SQLAlchemy Models."""

    @staticmethod
    def to_entity(model: Optional[DeviceModel]) -> Optional[Device]:
        """Chuyển đổi từ ORM Model sang Domain Entity."""
        if not model:
            return None

        # Reconstruct Domain Entity
        try:
            code = EquipmentCode(model.equip_code)

            # Xử lý an toàn cho Status
            status_val = model.equip_status
            try:
                status_enum = MachineStatus(int(status_val))
            except (ValueError, TypeError):
                status_enum = MachineStatus.UNKNOWN
        except Exception:
            return None

        device = Device(equipment_code=code)
        device.current_status = status_enum
        device.last_update = model.last_update

        if hasattr(device, "is_active"):
            device.is_active = model.is_active

        return device

    @staticmethod
    def to_model(entity: Device) -> DeviceModel:
        """Chuyển đổi từ Domain Entity sang ORM Model."""
        return DeviceModel(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=str(entity.current_status.value),
            last_update=entity.last_update or datetime.now(),
            is_active=getattr(entity, "is_active", True),
        )

    @staticmethod
    def to_entities(models: Sequence[DeviceModel]) -> List[Device]:
        return [OrmDeviceMapper.to_entity(m) for m in models if m is not None]

    # --- Status Period Mapping ---

    @staticmethod
    def to_period_entity(model: StatusPeriodModel) -> Optional[StatusPeriod]:
        if not model:
            return None
        return StatusPeriod(
            id=model.id,
            device_code=model.device_id,  # Mapping device_id as code here for simplicity
            status_code=model.status,
            start_time=model.start_time,
            end_time=model.end_time,
        )

    @staticmethod
    def to_period_model(entity: StatusPeriod) -> StatusPeriodModel:
        return StatusPeriodModel(
            id=entity.id or str(uuid.uuid4()),
            device_id=entity.device_code,
            status=entity.status_code,
            start_time=entity.start_time,
            end_time=entity.end_time,
        )
