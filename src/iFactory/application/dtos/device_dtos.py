from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DeviceStatusDTO:
    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime]
    material_batch: Optional[str]
    feeding_time: Optional[datetime]
    is_active: bool


@dataclass(frozen=True)
class GanttSegmentDTO:
    device_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
