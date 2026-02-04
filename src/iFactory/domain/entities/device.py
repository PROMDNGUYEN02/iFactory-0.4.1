# src/iFactory/domain/entities/device.py
"""
Device Aggregate Root.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..common.aggregate import AggregateRoot, AggregateSnapshot
from ..common.event import EventMetadata
from ..enums.machine_status import MachineStatus
from ..events.device_events import StatusChangedEvent
from ..exceptions.domain_exceptions import StaleDataError, InvalidTransitionError
from ..policies.transition_policy import StatusTransitionPolicy
from ..value_objects.equipment_code import EquipmentCode


@dataclass(frozen=True)
class DeviceState:
    """Immutable device state for snapshots."""

    equipment_code: str
    current_status: int
    last_updated_at: str
    equip_name: Optional[str]
    reason_code: Optional[str]
    version: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "equipment_code": self.equipment_code,
            "current_status": self.current_status,
            "last_updated_at": self.last_updated_at,
            "equip_name": self.equip_name,
            "reason_code": self.reason_code,
            "version": self.version,
        }


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

    @property
    def aggregate_id(self) -> str:
        return str(self._equipment_code)

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def register_new(
        cls,
        code: EquipmentCode,
        timestamp: Optional[datetime] = None,
        equip_name: Optional[str] = None,
    ) -> Device:
        return cls(
            equipment_code=code,
            current_status=MachineStatus.UNKNOWN,
            last_updated_at=timestamp or datetime.now(),
            equip_name=equip_name,
        )

    @classmethod
    def from_remote_data(
        cls,
        code: str,
        status_code: str,
        timestamp: datetime,
        equip_name: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> Device:
        equipment_code = EquipmentCode.create(code)
        status = MachineStatus.from_code(status_code)

        return cls(
            equipment_code=equipment_code,
            current_status=status,
            last_updated_at=timestamp,
            equip_name=equip_name,
            reason_code=reason_code,
        )

    # ========================================================================
    # Properties
    # ========================================================================

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

    @property
    def is_in_alarm(self) -> bool:
        return self._current_status == MachineStatus.ALARM

    @property
    def requires_attention(self) -> bool:
        return self._current_status in (
            MachineStatus.ALARM,
            MachineStatus.MAINTENANCE,
            MachineStatus.UNKNOWN,
        )

    # ========================================================================
    # Command Methods
    # ========================================================================

    def update_status(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        """Update status with transition policy enforcement."""
        self._transition_to(new_status, timestamp)

    def sync_status(
        self,
        observed_status: MachineStatus,
        observed_at: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> bool:
        """
        Synchronize status from external observation.
        Does NOT enforce transition policies.
        """
        if observed_at < self._last_updated_at:
            return False

        if self._current_status == observed_status:
            self._last_updated_at = observed_at
            return True

        event = StatusChangedEvent(
            occurred_at=observed_at,
            equipment_code=self._equipment_code,
            previous_status=self._current_status,
            new_status=observed_status,
        )
        self._record_event(event, metadata)

        self._current_status = observed_status
        self._last_updated_at = observed_at
        return True

    def update_remote_info(
        self,
        equip_name: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> None:
        """Update metadata from remote source."""
        if equip_name is not None:
            self._equip_name = equip_name
        if reason_code is not None:
            self._reason_code = reason_code

    def _transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        """Internal transition with policy enforcement."""
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
        self._record_event(event, metadata)

        self._current_status = new_status
        self._last_updated_at = timestamp

    # ========================================================================
    # Snapshot Support
    # ========================================================================

    def _get_snapshot_state(self) -> Dict[str, Any]:
        return DeviceState(
            equipment_code=str(self._equipment_code),
            current_status=self._current_status.value,
            last_updated_at=self._last_updated_at.isoformat(),
            equip_name=self._equip_name,
            reason_code=self._reason_code,
            version=self.version,
        ).to_dict()

    @classmethod
    def from_snapshot(cls, snapshot: AggregateSnapshot) -> Device:
        state = snapshot.state
        device = cls(
            equipment_code=EquipmentCode.create(state["equipment_code"]),
            current_status=MachineStatus(state["current_status"]),
            last_updated_at=datetime.fromisoformat(state["last_updated_at"]),
            equip_name=state.get("equip_name"),
            reason_code=state.get("reason_code"),
        )
        device.set_version(state.get("version", 0))
        return device

    # ========================================================================
    # Equality
    # ========================================================================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Device):
            return NotImplemented
        return self._equipment_code == other._equipment_code

    def __hash__(self) -> int:
        return hash(self._equipment_code)

    def __repr__(self) -> str:
        return f"Device(" f"code={self._equipment_code}, " f"status={self._current_status.name}, " f"v={self.version})"


__all__ = ["Device", "DeviceState"]
