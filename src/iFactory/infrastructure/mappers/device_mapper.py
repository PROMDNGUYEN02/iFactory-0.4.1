from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.infrastructure.database.models import DeviceORM


class DeviceMapper:
    """
    Pure functions to map between Device Domain Entity and SQLAlchemy DeviceORM.
    Contains strictly mapping logic, no business rules.
    """

    @staticmethod
    def to_entity(model: DeviceORM) -> Device:
        """Convert ORM model to domain entity."""
        return Device.create(
            code=model.equip_code,
            raw_status=model.equip_status,
            last_update=model.last_update,
        )

    @staticmethod
    def to_entities(models: Sequence[DeviceORM]) -> list[Device]:
        """Convert multiple ORM models to domain entities."""
        return [DeviceMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: Device) -> DeviceORM:
        """Convert domain entity to ORM model."""
        return DeviceORM(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_update or datetime.now(),
            is_active=True,
        )
