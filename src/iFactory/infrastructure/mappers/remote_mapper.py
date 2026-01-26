"""
Infrastructure Mappers for External Data.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Any

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.enums.machine_status import MachineStatus


class RemoteDeviceMapper:
    """Translates raw dictionary payloads from external APIs/DBs to Domain objects."""

    @staticmethod
    def from_raw_record(raw: Dict[str, Any], current_time: datetime) -> Device:
        """
        Creates a Device aggregate from a raw external record.
        Translates raw statuses to Domain statuses.
        """
        code = raw.get("equip_code", "")
        raw_status = raw.get("raw_status", "")
        last_time = raw.get("end_time") or raw.get("start_time") or current_time

        device = Device(equipment_code=EquipmentCode(code))

        # Domain object resolves business meaning
        device.report_sensor_status(raw_status, last_time)

        return device
