from __future__ import annotations

from datetime import datetime

from ..common.event import DomainEvent
from ..enums.machine_status import MachineStatus
from ..value_objects.equipment_code import EquipmentCode


class StatusChangedEvent(DomainEvent):
    """
    Event emitted when a device transitions to a new business status.
    """

    __slots__ = ("_equipment_code", "_previous_status", "_new_status")

    def __init__(
        self,
        occurred_at: datetime,
        equipment_code: EquipmentCode,
        previous_status: MachineStatus,
        new_status: MachineStatus,
    ) -> None:
        super().__init__(occurred_at)
        self._equipment_code = equipment_code
        self._previous_status = previous_status
        self._new_status = new_status

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
    def was_downtime_start(self) -> bool:
        return not self._previous_status.implies_downtime and self._new_status.implies_downtime

    @property
    def was_downtime_end(self) -> bool:
        return self._previous_status.implies_downtime and not self._new_status.implies_downtime
