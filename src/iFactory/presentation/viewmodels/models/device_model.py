# File: presentation/viewmodels/models/device_model.py
"""
Device Data Models.

Pure data classes for device information.
These are NOT ViewModels - they are immutable data containers
used by ViewModels to represent device state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class MaterialInputModel:
    """
    Immutable model for a single material input.

    Represents one material batch loaded into the device.
    """

    lot_no: str
    material_batch: str
    material_name: str
    feed_time: str  # ISO format string for display
    feed_qty: float = 0.0
    feed_user: str = ""

    @property
    def display_name(self) -> str:
        """Get shortened display name for UI."""
        if len(self.material_name) > 30:
            return self.material_name[:27] + "..."
        return self.material_name

    @property
    def formatted_time(self) -> str:
        """Get formatted time for display (HH:MM:SS)."""
        if not self.feed_time:
            return "--:--:--"
        try:
            # Parse ISO format and format as time only
            if "T" in self.feed_time:
                time_part = self.feed_time.split("T")[1]
            else:
                time_part = self.feed_time.split(" ")[-1] if " " in self.feed_time else self.feed_time

            # Take only HH:MM:SS
            return time_part[:8] if len(time_part) >= 8 else time_part
        except Exception:
            return self.feed_time[:8] if len(self.feed_time) >= 8 else self.feed_time

    @staticmethod
    def from_dict(data: dict) -> "MaterialInputModel":
        """Create from dictionary."""
        feed_time = data.get("feed_time", "")
        if isinstance(feed_time, datetime):
            feed_time = feed_time.isoformat()

        return MaterialInputModel(
            lot_no=data.get("lot_no", ""),
            material_batch=data.get("material_batch", ""),
            material_name=data.get("material_name", ""),
            feed_time=feed_time,
            feed_qty=float(data.get("feed_qty", 0)),
            feed_user=data.get("feed_user", ""),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "lot_no": self.lot_no,
            "material_batch": self.material_batch,
            "material_name": self.material_name,
            "feed_time": self.feed_time,
            "feed_qty": self.feed_qty,
            "feed_user": self.feed_user,
        }


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

    # Availability Data
    availability: float = 0.0  # Percentage (0-100)
    run_time_seconds: float = 0.0  # Total RUN time today
    total_time_seconds: float = 0.0  # Total time from 00:00 to now

    # Material Inputs - NEW
    material_inputs: tuple = field(default_factory=tuple)  # Tuple of MaterialInputModel
    current_lot_no: str = ""  # Current LOT_NO being processed

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

    @property
    def formatted_availability(self) -> str:
        """Format availability as percentage string."""
        return f"{self.availability:.1f}%"

    @property
    def formatted_run_time(self) -> str:
        """Format run time as HH:MM:SS."""
        total_seconds = int(self.run_time_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @property
    def has_material_inputs(self) -> bool:
        """Check if device has material inputs."""
        return len(self.material_inputs) > 0

    @property
    def material_input_count(self) -> int:
        """Get number of material inputs."""
        return len(self.material_inputs)

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

    def with_material_inputs(
        self,
        materials: List["MaterialInputModel"],
        lot_no: str = "",
    ) -> "DeviceDisplayModel":
        """
        Create a new DeviceDisplayModel with updated material inputs.

        Since this is immutable, returns a new instance.
        """
        # Update material_batch and feeding_time from first material if available
        material_batch = self.material_batch
        feeding_time = self.feeding_time

        if materials:
            first_mat = materials[0]
            material_batch = first_mat.material_batch
            feeding_time = first_mat.formatted_time

        return DeviceDisplayModel(
            device_id=self.device_id,
            display_name=self.display_name,
            status_code=self.status_code,
            status_name=self.status_name,
            status_color=self.status_color,
            status_emoji=self.status_emoji,
            is_running=self.is_running,
            requires_attention=self.requires_attention,
            last_update=self.last_update,
            input_count=self.input_count,
            output_count=self.output_count,
            error_count=self.error_count,
            oee=self.oee,
            yield_rate=self.yield_rate,
            cycle_time=self.cycle_time,
            description=self.description,
            material_batch=material_batch,
            feeding_time=feeding_time,
            last_error=self.last_error,
            availability=self.availability,
            run_time_seconds=self.run_time_seconds,
            total_time_seconds=self.total_time_seconds,
            material_inputs=tuple(materials),
            current_lot_no=lot_no,
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
            # Availability fields
            "availability": self.availability,
            "run_time_seconds": self.run_time_seconds,
            "total_time_seconds": self.total_time_seconds,
            # Material inputs - NEW
            "material_inputs": [m.to_dict() for m in self.material_inputs],
            "current_lot_no": self.current_lot_no,
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
    "MaterialInputModel",
]
