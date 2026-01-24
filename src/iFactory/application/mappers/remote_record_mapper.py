"""
Remote record to Domain entity mapper.
"""

import logging
from datetime import datetime
from typing import Optional, Union

from iFactory.application.interfaces import RemoteStatusRecord
from iFactory.domain.entities import Device
from iFactory.domain.value_objects import EquipmentCode, Status
from iFactory.domain.enums import DeviceStatus

logger = logging.getLogger(__name__)

__all__ = ["RemoteRecordMapper"]


class RemoteRecordMapper:
    """
    Maps remote data source records to Domain Entities.
    Responsibility: External Input (API/Dict) -> Domain Entity.
    """

    __slots__ = ()
    @staticmethod
    def to_device(
        record: Union[RemoteStatusRecord, dict],
    ) -> Optional[Device]:
        """
        Convert a remote record to a Domain Device entity.
        """
        try:
            if isinstance(record, dict):
                equip_code = record.get("equip_code")
                raw_status = str(record.get("equip_status", "0"))
                last_update = record.get("last_update")
            else:
                equip_code = record.equip_code
                raw_status = str(record.equip_status)
                last_update = record.last_update

            if not equip_code:
                logger.warning("[RemoteRecordMapper] Record missing equip_code")
                return None

            if last_update is None:
                last_update = datetime.now()

            normalized_status = DeviceStatus.from_code_or_name(raw_status)

            return Device(
                equipment_code=EquipmentCode(equip_code),
                current_status=Status(normalized_status),
                last_update=last_update,
            )

        except ValueError as e:
            logger.warning(f"[RemoteRecordMapper] Invalid record: {e}")
            return None
        except Exception as e:
            logger.error(f"[RemoteRecordMapper] Unexpected error: {e}", exc_info=True)
            return None

            if last_update is None:
                last_update = datetime.now()

            # Use StatusMapper utility to normalize incoming raw string
            from iFactory.application.mappers.status_period_mapper import StatusMapper

            normalized_status = StatusMapper.normalize(raw_status)

            return Device(
                equipment_code=EquipmentCode(equip_code),
                current_status=Status.from_code(normalized_status),
                last_update=last_update,
            )

        except ValueError as e:
            logger.warning(f"[RemoteRecordMapper] Invalid record: {e}")
            return None
        except Exception as e:
            logger.error(f"[RemoteRecordMapper] Unexpected error: {e}", exc_info=True)
            return None
