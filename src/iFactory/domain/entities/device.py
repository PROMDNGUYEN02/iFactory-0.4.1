# src/domain/entities/device.py - ENHANCED
"""
Enhanced Device Aggregate Root with Result pattern integration.

Features:
- Result pattern for error handling
- Enhanced event metadata
- Optimistic concurrency support
- Snapshot/restore for event sourcing
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

if TYPE_CHECKING:
    from iFactory.shared.core.result import Result, Error


# ============================================================================
# Device State (for snapshots)
# ============================================================================


@dataclass(frozen=True)
class DeviceState:
    """Immutable device state for snapshots and history."""

    equipment_code: str
    current_status: str
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


# ============================================================================
# Device Aggregate
# ============================================================================


class Device(AggregateRoot):
    """
    Aggregate Root representing a manufacturing device.

    Supports two modes of status update:
    1. Command-driven (update_status): Enforces transition policy, returns Result
    2. Sync-driven (sync_status): Observes external state without policy enforcement

    Features:
    - Result pattern for command operations
    - Optimistic concurrency via version
    - Event sourcing ready with snapshots
    - Rich domain events with metadata
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

    # ========================================================================
    # Aggregate Identity
    # ========================================================================

    @property
    def aggregate_id(self) -> str:
        """Unique identifier for this aggregate."""
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
    ) -> "Device":
        """
        Factory method to register a new device.

        Returns a new Device in UNKNOWN status.
        """
        device = cls(
            equipment_code=code,
            current_status=MachineStatus.UNKNOWN,
            last_updated_at=timestamp or datetime.now(),
            equip_name=equip_name,
        )
        return device

    @classmethod
    def from_remote_data(
        cls,
        code: str,
        status_code: str,
        timestamp: datetime,
        equip_name: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> "Device":
        """
        Factory method to create device from remote system data.
        """
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
        """Device is in an active (non-shutdown) state."""
        return self._current_status.is_active

    @property
    def is_operational(self) -> bool:
        """Device is currently running/producing."""
        return self._current_status.is_running

    @property
    def is_in_alarm(self) -> bool:
        """Device is in alarm state."""
        return self._current_status == MachineStatus.ALARM

    @property
    def requires_attention(self) -> bool:
        """Device requires operator attention."""
        return self._current_status in (
            MachineStatus.ALARM,
            MachineStatus.MAINTENANCE,
            MachineStatus.UNKNOWN,
        )

    # ========================================================================
    # Command Methods (Result pattern)
    # ========================================================================

    def try_start_production(
        self,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """
        Attempt to start production.

        Returns:
            Result.success(None) if transition succeeded
            Result.failure(Error) if transition failed
        """
        return self._try_transition_to(
            MachineStatus.RUNNING,
            timestamp,
            metadata,
        )

    def try_stop_production(
        self,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """Attempt to stop production."""
        return self._try_transition_to(
            MachineStatus.STOPPED,
            timestamp,
            metadata,
        )

    def try_shutdown(
        self,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """Attempt to shutdown device."""
        return self._try_transition_to(
            MachineStatus.SHUTDOWN,
            timestamp,
            metadata,
        )

    def try_enter_maintenance(
        self,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """Attempt to enter maintenance mode."""
        return self._try_transition_to(
            MachineStatus.MAINTENANCE,
            timestamp,
            metadata,
        )

    def try_trigger_alarm(
        self,
        timestamp: datetime,
        reason: Optional[str] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """Attempt to trigger alarm."""
        result = self._try_transition_to(
            MachineStatus.ALARM,
            timestamp,
            metadata,
        )
        if result.is_success and reason:
            self._reason_code = reason
        return result

    def try_clear_alarm(
        self,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """Attempt to clear alarm and return to stopped."""
        if self._current_status != MachineStatus.ALARM:
            from iFactory.shared.core.result import Result, Errors

            return Result.failure(
                Errors.validation(
                    "Can only clear alarm when in ALARM state",
                    field="current_status",
                )
            )

        result = self._try_transition_to(
            MachineStatus.STOPPED,
            timestamp,
            metadata,
        )
        if result.is_success:
            self._reason_code = None
        return result

    def try_update_status(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """
        Generic status update with transition policy enforcement.
        """
        return self._try_transition_to(new_status, timestamp, metadata)

    def _try_transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> "Result[None, Error]":
        """
        Internal transition with Result pattern.
        """
        from iFactory.shared.core.result import Result, Errors

        # Timestamp validation
        if timestamp < self._last_updated_at:
            return Result.failure(
                Errors.validation(
                    f"Timestamp {timestamp} is before last update {self._last_updated_at}",
                    field="timestamp",
                )
            )

        # Same status - just update timestamp
        if self._current_status == new_status:
            self._last_updated_at = timestamp
            return Result.success(None)

        # Validate transition
        try:
            StatusTransitionPolicy.validate(self._current_status, new_status)
        except InvalidTransitionError as e:
            return Result.failure(
                Errors.validation(
                    str(e),
                    field="status_transition",
                )
            )

        # Record event
        event = StatusChangedEvent(
            occurred_at=timestamp,
            equipment_code=self._equipment_code,
            previous_status=self._current_status,
            new_status=new_status,
        )
        self._record_event(event, metadata)

        # Update state
        self._current_status = new_status
        self._last_updated_at = timestamp

        return Result.success(None)

    # ========================================================================
    # Legacy Command Methods (raise exceptions)
    # ========================================================================

    def start_production(self, timestamp: datetime) -> None:
        """Start production. Raises on invalid transition."""
        self._transition_to(MachineStatus.RUNNING, timestamp)

    def stop_production(self, timestamp: datetime) -> None:
        """Stop production. Raises on invalid transition."""
        self._transition_to(MachineStatus.STOPPED, timestamp)

    def shutdown(self, timestamp: datetime) -> None:
        """Shutdown device. Raises on invalid transition."""
        self._transition_to(MachineStatus.SHUTDOWN, timestamp)

    def enter_maintenance(self, timestamp: datetime) -> None:
        """Enter maintenance. Raises on invalid transition."""
        self._transition_to(MachineStatus.MAINTENANCE, timestamp)

    def trigger_alarm(self, timestamp: datetime) -> None:
        """Trigger alarm. Raises on invalid transition."""
        self._transition_to(MachineStatus.ALARM, timestamp)

    def clear_alarm(self, timestamp: datetime) -> None:
        """Clear alarm. Raises on invalid transition."""
        self._transition_to(MachineStatus.STOPPED, timestamp)

    def update_status(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        """
        Update status with transition policy enforcement.
        Raises InvalidTransitionError if transition not allowed.
        """
        self._transition_to(new_status, timestamp)

    # ========================================================================
    # Sync Methods (observe external state)
    # ========================================================================

    def sync_status(
        self,
        observed_status: MachineStatus,
        observed_at: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> bool:
        """
        Synchronize status from external observation (e.g., SCADA/PLC).

        Does NOT enforce transition policies - we're observing reality.

        Args:
            observed_status: Status observed from external system
            observed_at: When observation was made
            metadata: Optional event metadata

        Returns:
            True if status was updated, False if ignored (stale data)
        """
        # Timestamp guard: reject out-of-order events
        if observed_at < self._last_updated_at:
            return False

        # Same status: just update timestamp
        if self._current_status == observed_status:
            self._last_updated_at = observed_at
            return True

        # Record domain event
        event = StatusChangedEvent(
            occurred_at=observed_at,
            equipment_code=self._equipment_code,
            previous_status=self._current_status,
            new_status=observed_status,
        )
        self._record_event(event, metadata)

        # Update state
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

    # ========================================================================
    # Internal Behavior
    # ========================================================================

    def _transition_to(
        self,
        new_status: MachineStatus,
        timestamp: datetime,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        """
        Internal transition with full policy enforcement.
        Raises exceptions on failure.
        """
        if timestamp < self._last_updated_at:
            raise StaleDataError.timestamp_regression(
                self._last_updated_at,
                timestamp,
            )

        if self._current_status == new_status:
            self._last_updated_at = timestamp
            return

        # Enforce transition policy
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
    # Invariant Validation
    # ========================================================================

    def _validate_invariants(self) -> None:
        """Validate device invariants."""
        # Equipment code must be valid
        if not self._equipment_code:
            raise ValueError("Device must have equipment code")

        # Status must be valid
        if self._current_status is None:
            raise ValueError("Device must have a status")

    # ========================================================================
    # Snapshot Support
    # ========================================================================

    def _get_snapshot_state(self) -> Dict[str, Any]:
        """Get state for snapshot."""
        return DeviceState(
            equipment_code=str(self._equipment_code),
            current_status=self._current_status.value,
            last_updated_at=self._last_updated_at.isoformat(),
            equip_name=self._equip_name,
            reason_code=self._reason_code,
            version=self.version,
        ).to_dict()

    @classmethod
    def from_snapshot(cls, snapshot: AggregateSnapshot) -> "Device":
        """Restore device from snapshot."""
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
    # Equality & Representation
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
