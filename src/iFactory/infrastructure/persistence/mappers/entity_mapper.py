from __future__ import annotations
from datetime import datetime
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status import Status
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.infrastructure.database.models.hot_models import DeviceStateModel, DeviceInputModel
from iFactory.infrastructure.database.models.cold_models import StatusHistoryModel, InputHistoryModel


class EntityMapper:
    @staticmethod
    def to_device_entity(model: DeviceStateModel) -> Device:
        return Device.create(code=model.equip_code, status=model.equip_status, last_update=model.last_update)

    @staticmethod
    def to_status_period_entity(model: StatusHistoryModel) -> StatusPeriod:
        return StatusPeriod(
            equipment_code=EquipmentCode(model.equip_code),
            status=Status.normalize(model.equip_status),
            time_range=TimeRange(model.start_time, model.end_time or datetime.now()),
        )

    @staticmethod
    def to_material_input_entity(model: DeviceInputModel | InputHistoryModel) -> MaterialInput:
        return MaterialInput.create(model.equip_code, model.material_batch, model.feeding_time)
