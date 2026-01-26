from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class DeviceStatusDTO:
    """
    Read-only projection of Device Status.
    Contains NO UI logic (no colors, no translations).
    """

    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime] = None
    material_batch: Optional[str] = None
    feeding_time: Optional[datetime] = None
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class DeviceHistoryDTO:
    """Projection for device history logs."""

    equip_code: str
    status_code: str
    timestamp: datetime
