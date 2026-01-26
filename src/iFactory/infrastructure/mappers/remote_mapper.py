"""
Infrastructure Mapper for External/Remote Data.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode


class RemoteDeviceMapper:
    """Translates raw dictionary payloads from external APIs/DBs to Domain objects."""

    @staticmethod
    def from_raw_record(raw: Dict[str, Any], current_time: datetime) -> Device:
        code = raw.get("equip_code", "")
        raw_status = raw.get("raw_status", "")
        last_time = raw.get("end_time") or raw.get("start_time") or current_time

        device = Device(equipment_code=EquipmentCode(code))

        # Domain Aggregate resolves the business meaning of the external string
        device.report_sensor_status(raw_status, last_time)

        return device
