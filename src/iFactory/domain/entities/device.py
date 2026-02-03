# File: domain/entities/device.py
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

    Supports two modes of status update:
    1. Command-driven (update_status): Enforces transition policy
    2. Sync-driven (sync_status): Observes external state without policy enforcement
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

    # --- Command Methods (enforce transition policy) ---

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
        Update status with transition policy enforcement.

        Use this for command-driven changes (e.g., operator actions).
        Raises InvalidTransitionError if the transition is not allowed.
        """
        self._transition_to(new_status, timestamp)

    # --- Sync Methods (observe external state) ---

    def sync_status(
        self,
        observed_status: MachineStatus,
        observed_at: datetime,
    ) -> bool:
        """
        Synchronize status from an external observation (e.g., SCADA/PLC).

        This method is for syncing observed state from external systems.
        It does NOT enforce transition policies because we are observing
        reality, not commanding a change.

        Args:
            observed_status: The status observed from the external system.
            observed_at: When the observation was made.

        Returns:
            True if the status was updated, False if ignored (stale data).

        Note:
            - Ignores out-of-order events (timestamp guard)
            - Does NOT enforce transition policy
            - Emits domain event on actual change
        """
        # Timestamp guard: reject out-of-order events
        if observed_at < self._last_updated_at:
            return False  # Stale data, silently ignore

        # Same status: just update timestamp
        if self._current_status == observed_status:
            self._last_updated_at = observed_at
            return True

        # Record domain event for actual state change
        event = StatusChangedEvent(
            occurred_at=observed_at,
            equipment_code=self._equipment_code,
            previous_status=self._current_status,
            new_status=observed_status,
        )
        self._record_event(event)

        # Update state
        self._current_status = observed_status
        self._last_updated_at = observed_at
        return True

    def update_remote_info(self, equip_name: Optional[str], reason_code: Optional[str]) -> None:
        """Update metadata from remote source."""
        if equip_name is not None:
            self._equip_name = equip_name
        if reason_code is not None:
            self._reason_code = reason_code

    # --- Internal Behavior ---

    def _transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        """
        Internal transition with full policy enforcement.
        Used by command methods.
        """
        if timestamp < self._last_updated_at:
            raise StaleDataError.timestamp_regression(self._last_updated_at, timestamp)

        if self._current_status == new_status:
            self._last_updated_at = timestamp
            return

        # Enforce transition policy (may raise InvalidTransitionError)
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
