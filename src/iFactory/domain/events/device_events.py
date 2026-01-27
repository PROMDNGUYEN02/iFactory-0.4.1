from __future__ import annotations

from datetime import datetime

from .base import DomainEvent
from ..enums.machine_status import MachineStatus


class StatusChangedEvent(DomainEvent):
    """
    Event emitted when a device transitions to a new business status.

    Contains both the previous and new status for audit trail
    and downstream processing.
    """

    __slots__ = ("_equipment_code", "_previous_status", "_new_status")

    def __init__(
        self,
        occurred_at: datetime,
        equipment_code: str,
        previous_status: MachineStatus,
        new_status: MachineStatus,
    ) -> None:
        super().__init__(occurred_at)
        self._equipment_code = equipment_code
        self._previous_status = previous_status
        self._new_status = new_status

    @property
    def equipment_code(self) -> str:
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StatusChangedEvent):
            return NotImplemented
        return (
            super().__eq__(other)
            and self._equipment_code == other._equipment_code
            and self._previous_status == other._previous_status
            and self._new_status == other._new_status
        )

    def __hash__(self) -> int:
        return hash(
            (
                super().__hash__(),
                self._equipment_code,
                self._previous_status,
                self._new_status,
            )
        )

    def __repr__(self) -> str:
        return (
            f"StatusChangedEvent("
            f"equipment_code={self._equipment_code!r}, "
            f"previous={self._previous_status.name}, "
            f"new={self._new_status.name}, "
            f"at={self.occurred_at!r})"
        )
