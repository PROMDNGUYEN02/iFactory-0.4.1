# src/iFactory/domain/events/device_events.py
"""
Device Domain Events.

Events that occur within the Device aggregate.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Dict, Optional

from ..common.event import DomainEvent, EventMetadata
from ..enums.machine_status import MachineStatus
from ..value_objects.equipment_code import EquipmentCode


class DeviceEvent(DomainEvent):
    """Base class for all device-related events."""

    __slots__ = ("_equipment_code",)

    def __init__(
        self,
        equipment_code: EquipmentCode,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        super().__init__(occurred_at=occurred_at, metadata=metadata)
        object.__setattr__(self, "_equipment_code", equipment_code)

    @property
    def equipment_code(self) -> EquipmentCode:
        """The device this event relates to."""
        return self._equipment_code

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["equipment_code"] = str(self._equipment_code)
        return data


class StatusChangedEvent(DeviceEvent):
    """
    Event emitted when a device transitions to a new status.

    This is one of the most important domain events as it:
    - Triggers history recording
    - May trigger notifications
    - Affects OEE calculations
    """

    VERSION: ClassVar[int] = 1

    __slots__ = ("_previous_status", "_new_status", "_reason_code")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        previous_status: MachineStatus,
        new_status: MachineStatus,
        occurred_at: Optional[datetime] = None,
        reason_code: Optional[str] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        super().__init__(
            equipment_code=equipment_code,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        object.__setattr__(self, "_previous_status", previous_status)
        object.__setattr__(self, "_new_status", new_status)
        object.__setattr__(self, "_reason_code", reason_code)

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def previous_status(self) -> MachineStatus:
        """Status before the transition."""
        return self._previous_status

    @property
    def new_status(self) -> MachineStatus:
        """Status after the transition."""
        return self._new_status

    @property
    def reason_code(self) -> Optional[str]:
        """Optional reason for the transition."""
        return self._reason_code

    # ========================================================================
    # Derived Properties
    # ========================================================================

    @property
    def was_downtime_start(self) -> bool:
        """True if this transition started a downtime period."""
        return not self._previous_status.implies_downtime and self._new_status.implies_downtime

    @property
    def was_downtime_end(self) -> bool:
        """True if this transition ended a downtime period."""
        return self._previous_status.implies_downtime and not self._new_status.implies_downtime

    @property
    def was_alarm_triggered(self) -> bool:
        """True if device went into alarm state."""
        return self._previous_status != MachineStatus.ALARM and self._new_status == MachineStatus.ALARM

    @property
    def was_alarm_cleared(self) -> bool:
        """True if device exited alarm state."""
        return self._previous_status == MachineStatus.ALARM and self._new_status != MachineStatus.ALARM

    @property
    def started_running(self) -> bool:
        """True if device started running."""
        return self._previous_status != MachineStatus.RUNNING and self._new_status == MachineStatus.RUNNING

    @property
    def stopped_running(self) -> bool:
        """True if device stopped running."""
        return self._previous_status == MachineStatus.RUNNING and self._new_status != MachineStatus.RUNNING

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "previous_status": self._previous_status.value,
                "previous_status_name": self._previous_status.name,
                "new_status": self._new_status.value,
                "new_status_name": self._new_status.name,
                "reason_code": self._reason_code,
                "was_downtime_start": self.was_downtime_start,
                "was_downtime_end": self.was_downtime_end,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatusChangedEvent":
        """Deserialize from dictionary."""
        return cls(
            equipment_code=EquipmentCode.create(data["equipment_code"]),
            previous_status=MachineStatus(data["previous_status"]),
            new_status=MachineStatus(data["new_status"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            reason_code=data.get("reason_code"),
            metadata=EventMetadata.from_dict(data.get("metadata", {})),
        )

    def with_metadata(self, metadata: EventMetadata) -> "StatusChangedEvent":
        """Create copy with new metadata."""
        return StatusChangedEvent(
            equipment_code=self._equipment_code,
            previous_status=self._previous_status,
            new_status=self._new_status,
            occurred_at=self._occurred_at,
            reason_code=self._reason_code,
            metadata=metadata,
        )

    def __repr__(self) -> str:
        return f"StatusChangedEvent(" f"device={self._equipment_code}, " f"{self._previous_status.name} → {self._new_status.name})"


class DeviceRegisteredEvent(DeviceEvent):
    """Event emitted when a new device is registered."""

    VERSION: ClassVar[int] = 1

    __slots__ = ("_initial_status", "_equip_name")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        initial_status: MachineStatus = MachineStatus.UNKNOWN,
        equip_name: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        super().__init__(
            equipment_code=equipment_code,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        object.__setattr__(self, "_initial_status", initial_status)
        object.__setattr__(self, "_equip_name", equip_name)

    @property
    def initial_status(self) -> MachineStatus:
        return self._initial_status

    @property
    def equip_name(self) -> Optional[str]:
        return self._equip_name

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "initial_status": self._initial_status.value,
                "initial_status_name": self._initial_status.name,
                "equip_name": self._equip_name,
            }
        )
        return data

    def with_metadata(self, metadata: EventMetadata) -> "DeviceRegisteredEvent":
        return DeviceRegisteredEvent(
            equipment_code=self._equipment_code,
            initial_status=self._initial_status,
            equip_name=self._equip_name,
            occurred_at=self._occurred_at,
            metadata=metadata,
        )


class DeviceAlarmTriggeredEvent(DeviceEvent):
    """Event emitted when a device enters alarm state."""

    VERSION: ClassVar[int] = 1

    __slots__ = ("_alarm_code", "_alarm_message", "_severity")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        alarm_code: str,
        alarm_message: Optional[str] = None,
        severity: str = "HIGH",
        occurred_at: Optional[datetime] = None,
        metadata: Optional[EventMetadata] = None,
    ) -> None:
        super().__init__(
            equipment_code=equipment_code,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        object.__setattr__(self, "_alarm_code", alarm_code)
        object.__setattr__(self, "_alarm_message", alarm_message)
        object.__setattr__(self, "_severity", severity)

    @property
    def alarm_code(self) -> str:
        return self._alarm_code

    @property
    def alarm_message(self) -> Optional[str]:
        return self._alarm_message

    @property
    def severity(self) -> str:
        return self._severity

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "alarm_code": self._alarm_code,
                "alarm_message": self._alarm_message,
                "severity": self._severity,
            }
        )
        return data

    def with_metadata(self, metadata: EventMetadata) -> "DeviceAlarmTriggeredEvent":
        return DeviceAlarmTriggeredEvent(
            equipment_code=self._equipment_code,
            alarm_code=self._alarm_code,
            alarm_message=self._alarm_message,
            severity=self._severity,
            occurred_at=self._occurred_at,
            metadata=metadata,
        )


__all__ = [
    "DeviceEvent",
    "StatusChangedEvent",
    "DeviceRegisteredEvent",
    "DeviceAlarmTriggeredEvent",
]
