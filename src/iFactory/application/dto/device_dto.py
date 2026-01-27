from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DeviceDTO:
    """
    Detailed Data Transfer Object for a Device.
    Used for full details views or edits.
    """

    equipment_code: str
    status_code: int
    status_name: str
    is_active: bool
    last_updated: datetime
    name: Optional[str] = None
    description: Optional[str] = None


@dataclass(frozen=True)
class DeviceSummaryDTO:
    """
    Lightweight DTO for lists and dashboards.
    """

    equipment_code: str
    status_code: int
    status_name: str
    last_updated: datetime
