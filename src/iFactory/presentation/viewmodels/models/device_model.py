"""
Device Data Models.

Pure data classes for device information.
These are NOT ViewModels - they are immutable data containers
used by ViewModels to represent device state.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class DeviceDisplayModel:
    """
    Immutable display model for a single device.

    Contains all data needed to render a device in the UI.
    This is a pure data container with no behavior.
    """

    device_id: str
    display_name: str
    status_code: int
    status_name: str
    status_color: str
    status_emoji: str
    is_running: bool
    requires_attention: bool
    last_update: Optional[str] = None
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    oee: float = 0.0
    yield_rate: float = 0.0
    cycle_time: float = 0.0
    description: str = ""
    material_batch: str = "--"
    feeding_time: str = "--"
    last_error: Optional[str] = None

    @property
    def id(self) -> str:
        return self.device_id

    @property
    def formatted_oee(self) -> str:
        return f"{self.oee:.1f}%"

    @property
    def formatted_yield(self) -> str:
        return f"{self.yield_rate:.1f}%"

    @property
    def formatted_cycle_time(self) -> str:
        return f"{self.cycle_time:.2f}s"

    @staticmethod
    def empty(device_id: str) -> "DeviceDisplayModel":
        """Create an empty device model with default values."""
        from ...constants.status import Status, StatusCode

        return DeviceDisplayModel(
            device_id=device_id,
            display_name=device_id,
            status_code=StatusCode.UNKNOWN,
            status_name=Status.get_name(StatusCode.UNKNOWN),
            status_color=Status.get_color(StatusCode.UNKNOWN),
            status_emoji=Status.get_emoji(StatusCode.UNKNOWN),
            is_running=False,
            requires_attention=False,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for state storage."""
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "status_color": self.status_color,
            "status_emoji": self.status_emoji,
            "is_running": self.is_running,
            "requires_attention": self.requires_attention,
            "last_update": self.last_update,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "error_count": self.error_count,
            "oee": self.oee,
            "yield_rate": self.yield_rate,
            "cycle_time": self.cycle_time,
            "description": self.description,
            "material_batch": self.material_batch,
            "feeding_time": self.feeding_time,
            "last_error": self.last_error,
            "equip_name": self.display_name,
        }


@dataclass(frozen=True, slots=True)
class DeviceSelectionModel:
    """Model for device selection state."""

    selected_device_id: Optional[str] = None
    is_panel_open: bool = False

    @property
    def has_selection(self) -> bool:
        return self.selected_device_id is not None


@dataclass(frozen=True, slots=True)
class DeviceSyncStatusModel:
    """Model for sync status."""

    is_syncing: bool = False
    last_sync_time: Optional[str] = None
    synced_count: int = 0
    error_message: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error_message is not None


__all__ = [
    "DeviceDisplayModel",
    "DeviceSelectionModel",
    "DeviceSyncStatusModel",
]
