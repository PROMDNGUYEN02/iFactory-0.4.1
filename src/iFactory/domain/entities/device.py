from __future__ import annotations

from datetime import datetime
from typing import Optional

from .aggregate_root import AggregateRoot
from ..enums.machine_status import MachineStatus
from ..events.device_events import StatusChangedEvent
from ..policies.status_transition_policy import StatusTransitionPolicy
from ..value_objects.equipment_code import EquipmentCode


class Device(AggregateRoot):
    """
    Aggregate Root representing a manufacturing device.

    Enforces business invariants for state transitions and encapsulates
    all device lifecycle operations.
    """

    __slots__ = (
        "_equipment_code",
        "_current_status",
        "_last_updated_at",
        "_name",
        "_description",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        current_status: MachineStatus = MachineStatus.UNKNOWN,
        last_updated_at: Optional[datetime] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._equipment_code = equipment_code
        self._current_status = current_status
        self._last_updated_at = last_updated_at or datetime.now()
        self._name = name
        self._description = description

    @classmethod
    def register_new(
        cls,
        code: EquipmentCode,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Device:
        """Factory method to register a new device in the system."""
        return cls(
            equipment_code=code,
            name=name,
            description=description,
            current_status=MachineStatus.UNKNOWN,
            last_updated_at=datetime.now(),
        )

    @property
    def equipment_code(self) -> EquipmentCode:
        return self._equipment_code

    @property
    def current_status(self) -> MachineStatus:
        return self._current_status

    @property
    def last_updated_at(self) -> datetime:
        return self._last_updated_at

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def is_active(self) -> bool:
        return self._current_status.is_active

    @property
    def is_operational(self) -> bool:
        return self._current_status.is_running

    @property
    def requires_attention(self) -> bool:
        return self._current_status.requires_attention

    def start_production(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.RUNNING, timestamp)

    def stop_production(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.STOPPED, timestamp)

    def shutdown(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.SHUTDOWN, timestamp)

    def enter_maintenance(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.MAINTENANCE, timestamp)

    def trigger_alarm(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.ALARM, timestamp)

    def clear_alarm(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.STOPPED, timestamp)

    def acknowledge_alarm(self, timestamp: datetime) -> None:
        if self._current_status == MachineStatus.ALARM:
            self._transition_to(MachineStatus.STOPPED, timestamp)

    def update_status(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        """
        Updates the device status from an external source (e.g., sensor).
        """
        self._transition_to(new_status, timestamp)

    def update_metadata(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if name is not None:
            self._name = name
        if description is not None:
            self._description = description

    def _transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        if self._current_status == new_status:
            return

        StatusTransitionPolicy.validate(self._current_status, new_status)

        event = StatusChangedEvent(
            occurred_at=timestamp,
            equipment_code=self._equipment_code,
            previous_status=self._current_status,
            new_status=new_status,
        )
        self._record_event(event)

        self._current_status = new_status
        self._last_updated_at = timestamp

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Device):
            return NotImplemented
        return self._equipment_code == other._equipment_code

    def __hash__(self) -> int:
        return hash(self._equipment_code)

    def __repr__(self) -> str:
        return f"Device(code={self._equipment_code}, " f"status={self._current_status.name}, " f"last_updated={self._last_updated_at})"
