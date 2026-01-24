"""
Device status DTO - Immutable data transfer object for device status.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

__all__ = ["DeviceStatusDTO"]


@dataclass(frozen=True, slots=True)
class DeviceStatusDTO:
    """
    Immutable device status DTO for API/UI communication.
    """

    equip_code: str
    status_code: str
    status_name: str
    status_display: str
    status_color: str
    last_update: datetime | None = None
    material_batch: str | None = None
    feeding_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the DTO to a dictionary for JSON serialization."""
        return {
            "equip_code": self.equip_code,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "status_display": self.status_display,
            "status_color": self.status_color,
            "last_update": (self.last_update.isoformat() if self.last_update else None),
            "material_batch": self.material_batch,
            "feeding_time": (self.feeding_time.isoformat() if self.feeding_time else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceStatusDTO":
        """Create DTO from dictionary (e.g., from Cache)."""
        return cls(
            equip_code=data.get("equip_code", ""),
            status_code=data.get("status_code", "0"),
            status_name=data.get("status_name", "unknown"),
            status_display=data.get("status_display", "UNKNOWN"),
            status_color=data.get("status_color", "#cccccc"),
            last_update=datetime.fromisoformat(data["last_update"]) if data.get("last_update") else None,
            material_batch=data.get("material_batch"),
            feeding_time=datetime.fromisoformat(data["feeding_time"]) if data.get("feeding_time") else None,
        )
