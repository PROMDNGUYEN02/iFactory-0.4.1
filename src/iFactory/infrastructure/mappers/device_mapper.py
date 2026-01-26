"""
Infrastructure Mappers for Database ORM.
"""

from __future__ import annotations
from datetime import datetime
from typing import Sequence

from iFactory.domain.entities.device import Device
from iFactory.infrastructure.persistence.models import DeviceORM
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode


class DeviceMapper:
    """Bi-directional mapping between Domain Aggregate and ORM Model."""

    @staticmethod
    def to_entity(model: DeviceORM) -> Device:
        """Hydrate a domain entity from DB model."""
        device = Device(equipment_code=EquipmentCode(model.equip_code))
        device.current_status = MachineStatus(model.equip_status)
        device.last_update = model.last_update
        return device

    @staticmethod
    def to_model(entity: Device) -> DeviceORM:
        """Dehydrate a domain entity to DB model."""
        return DeviceORM(
            id=entity.equipment_code.value,
            equip_code=entity.equipment_code.value,
            equip_status=entity.current_status.value,
            last_update=entity.last_update or datetime.now(),
            is_active=True,
        )

    @staticmethod
    def to_entities(models: Sequence[DeviceORM]) -> list[Device]:
        return [DeviceMapper.to_entity(m) for m in models]
