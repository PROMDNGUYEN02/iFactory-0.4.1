# src/iFactory/domain/events/device_events.py
"""
Device Domain Events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Dict, Optional

from ..common.event import DomainEvent, EventMetadata
from ..enums.machine_status import MachineStatus
from ..value_objects.equipment_code import EquipmentCode


class StatusChangedEvent(DomainEvent):
    """Event emitted when a device transitions to a new status."""

    VERSION: ClassVar[int] = 1

    __slots__ = ("_equipment_code", "_previous_status", "_new_status", "_reason_code")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        previous_status: MachineStatus,
        new_status: MachineStatus,
        occurred_at: Optional[datetime] = None,
        reason_code: Optional[str] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        super().__init__(occurred_at=occurred_at, metadata=metadata)
        self._equipment_code = equipment_code
        self._previous_status = previous_status
        self._new_status = new_status
        self._reason_code = reason_code

    @property
    def equipment_code(self) -> EquipmentCode:
        return self._equipment_code

    @property
    def previous_status(self) -> MachineStatus:
        return self._previous_status

    @property
    def new_status(self) -> MachineStatus:
        return self._new_status

    @property
    def reason_code(self) -> Optional[str]:
        return self._reason_code

    @property
    def was_downtime_start(self) -> bool:
        return not self._previous_status.implies_downtime and self._new_status.implies_downtime

    @property
    def was_downtime_end(self) -> bool:
        return self._previous_status.implies_downtime and not self._new_status.implies_downtime

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "equipment_code": str(self._equipment_code),
                "previous_status": self._previous_status.value,
                "previous_status_name": self._previous_status.name,
                "new_status": self._new_status.value,
                "new_status_name": self._new_status.name,
                "reason_code": self._reason_code,
            }
        )
        return data

    def with_metadata(self, metadata: EventMetadata) -> StatusChangedEvent:
        return StatusChangedEvent(
            equipment_code=self._equipment_code,
            previous_status=self._previous_status,
            new_status=self._new_status,
            occurred_at=self._occurred_at,
            reason_code=self._reason_code,
            metadata=metadata,
        )

    def __repr__(self) -> str:
        return f"StatusChangedEvent(" f"device={self._equipment_code}, " f"{self._previous_status.name}->{self._new_status.name})"


__all__ = ["StatusChangedEvent"]
