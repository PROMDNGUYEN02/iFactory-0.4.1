"""
Remote record to Domain entity mapper.
Strict Clean Architecture: Pure function mapping external data (dict) to Domain Entity.
"""

import logging
from datetime import datetime
from typing import Optional

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status import Status
from iFactory.domain.enums.device_status import DeviceStatus

logger = logging.getLogger(__name__)

__all__ = ["to_device_entity"]


def to_device_entity(record: dict) -> Optional[Device]:
    """
    Convert a raw remote record (dict) to a Domain Device entity.

    Args:
        record (dict): Raw data from external API/Database.

    Returns:
        Optional[Device]: The mapped Domain Entity, or None if validation fails.
    """
    try:
        equip_code = record.get("equip_code")
        raw_status = str(record.get("equip_status", "0"))
        last_update = record.get("last_update")

        if not equip_code:
            logger.warning("[RemoteRecordMapper] Record missing equip_code")
            return None

        if last_update is None:
            last_update = datetime.now()

        # Normalize status using Domain rules
        normalized_status = DeviceStatus.from_code_or_name(raw_status)

        return Device(
            equipment_code=EquipmentCode(equip_code),
            current_status=Status(normalized_status),
            last_update=last_update,
        )

    except ValueError as e:
        logger.warning(f"[RemoteRecordMapper] Invalid record data: {e}")
        return None
    except Exception as e:
        logger.error(f"[RemoteRecordMapper] Unexpected mapping error: {e}", exc_info=True)
        return None
