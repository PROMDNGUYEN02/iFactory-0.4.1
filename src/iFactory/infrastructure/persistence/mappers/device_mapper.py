from __future__ import annotations
from datetime import datetime
from typing import Sequence
from iFactory.domain.entities import Device
from iFactory.infrastructure.database.models.hot_models import LatestStatus


class DeviceMapper:
    @staticmethod
    def to_entity(model: LatestStatus) -> Device:
        return Device.create(
            code=model.equip_code,
            status=model.equip_status,
            last_update=model.last_update,
        )

    @staticmethod
    def to_entities(models: Sequence[LatestStatus]) -> list[Device]:
        return [DeviceMapper.to_entity(m) for m in models]

    @staticmethod
    def to_model(entity: Device) -> LatestStatus:
        return LatestStatus(
            equip_code=entity.code,
            equip_status=entity.current_status.code,
            last_update=entity.last_update or datetime.now(),
        )
