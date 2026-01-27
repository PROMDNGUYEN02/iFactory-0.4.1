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
        "_last_update",
        "_name",
        "_description",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        current_status: MachineStatus = MachineStatus.UNKNOWN,
        last_update: Optional[datetime] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._equipment_code = equipment_code
        self._current_status = current_status
        self._last_update = last_update
        self._name = name
        self._description = description

    @classmethod
    def create(
        cls,
        code: str,
        raw_status: str | int,
        last_update: Optional[datetime] = None,
    ) -> Device:
        """
        Factory method to reconstruct entity from infrastructure data.
        Used by repositories and sync commands.
        """
        status = MachineStatus.from_raw_value(raw_status)
        return cls(
            equipment_code=EquipmentCode(code),
            current_status=status,
            last_update=last_update or datetime.now(),
        )

    @classmethod
    def register_new(
        cls,
        code: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Device:
        """Factory method to register a new device in the system."""
        return cls(
            equipment_code=EquipmentCode(code),
            name=name,
            description=description,
            current_status=MachineStatus.UNKNOWN,
            last_update=datetime.now(),
        )

    @property
    def equipment_code(self) -> EquipmentCode:
        return self._equipment_code

    @property
    def current_status(self) -> MachineStatus:
        return self._current_status

    @property
    def last_update(self) -> Optional[datetime]:
        return self._last_update

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def code(self) -> str:
        return self._equipment_code.value

    @property
    def status(self) -> int:
        return self._current_status.value

    @property
    def status_name(self) -> str:
        return self._current_status.display_name

    @property
    def is_active(self) -> bool:
        return self._current_status.is_active

    @property
    def is_operational(self) -> bool:
        return self._current_status.is_running

    @property
    def is_idle(self) -> bool:
        return self._current_status.is_idle

    @property
    def requires_attention(self) -> bool:
        return self._current_status.requires_attention

    @property
    def implies_downtime(self) -> bool:
        return self._current_status.implies_downtime

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

    def acknowledge(self, timestamp: datetime) -> None:
        if self._current_status == MachineStatus.ALARM:
            self._transition_to(MachineStatus.STOPPED, timestamp)

    def report_sensor_status(
        self,
        raw_status: str | int,
        timestamp: datetime,
    ) -> None:
        new_status = MachineStatus.from_raw_value(raw_status)
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
            equipment_code=self._equipment_code.value,
            previous_status=self._current_status,
            new_status=new_status,
        )
        self._record_event(event)

        self._current_status = new_status
        self._last_update = timestamp

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Device):
            return NotImplemented
        return self._equipment_code == other._equipment_code

    def __hash__(self) -> int:
        return hash(self._equipment_code)

    def __repr__(self) -> str:
        return f"Device(code={self.code!r}, " f"status={self.status_name!r}, " f"last_update={self._last_update!r})"
