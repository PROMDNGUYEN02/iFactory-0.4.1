from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DeviceStatusDTO:
    device_id: str
    name: str
    equipment_code: str
    current_status: str
    is_active: bool
    last_updated: datetime


@dataclass(frozen=True)
class GanttSegmentDTO:
    device_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
