import logging
from datetime import datetime
from typing import Optional
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status import Status
from iFactory.domain.enums.device_status import DeviceStatus

logger = logging.getLogger(__name__)


def to_device_entity(record: dict) -> Optional[Device]:
    try:
        equip_code = record.get("equip_code")
        raw_status = str(record.get("equip_status", "0"))
        last_update = record.get("last_update") or datetime.now()

        if not equip_code:
            return None

        normalized_status = DeviceStatus.from_code_or_name(raw_status)
        return Device(
            equipment_code=EquipmentCode(equip_code),
            current_status=Status(normalized_status),
            last_update=last_update,
        )
    except Exception as e:
        logger.error(f"Mapping error: {e}")
        return None
