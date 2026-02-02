from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..common.aggregate import AggregateRoot
from ..enums.machine_status import MachineStatus
from ..events.device_events import StatusChangedEvent
from ..exceptions.domain_exceptions import StaleDataError
from ..policies.transition_policy import StatusTransitionPolicy
from ..value_objects.equipment_code import EquipmentCode


class Device(AggregateRoot):
    """
    Aggregate Root representing a manufacturing device.
    """

    __slots__ = (
        "_equipment_code",
        "_current_status",
        "_last_updated_at",
        "_equip_name",
        "_reason_code",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        current_status: MachineStatus,
        last_updated_at: datetime,
        equip_name: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._equipment_code = equipment_code
        self._current_status = current_status
        self._last_updated_at = last_updated_at
        self._equip_name = equip_name
        self._reason_code = reason_code

    @classmethod
    def register_new(
        cls,
        code: EquipmentCode,
        timestamp: datetime,
        equip_name: Optional[str] = None,
    ) -> Device:
        """
        Factory method to register a new device in the system.
        """
        return cls(
            equipment_code=code,
            equip_name=equip_name,
            current_status=MachineStatus.UNKNOWN,
            last_updated_at=timestamp,
        )

    # --- Properties ---

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
    def equip_name(self) -> Optional[str]:
        return self._equip_name

    @property
    def reason_code(self) -> Optional[str]:
        return self._reason_code

    @property
    def is_active(self) -> bool:
        return self._current_status.is_active

    @property
    def is_operational(self) -> bool:
        return self._current_status.is_running

    # --- Commands ---

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
        self._transition_to(new_status, timestamp)

    def update_remote_info(self, equip_name: Optional[str], reason_code: Optional[str]) -> None:
        self._equip_name = equip_name
        self._reason_code = reason_code

    # --- Internal Behavior ---

    def _transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        if timestamp < self._last_updated_at:
            raise StaleDataError.timestamp_regression(self._last_updated_at, timestamp)

        if self._current_status == new_status:
            self._last_updated_at = timestamp
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
        return f"Device(code={self._equipment_code}, status={self._current_status.name})"
