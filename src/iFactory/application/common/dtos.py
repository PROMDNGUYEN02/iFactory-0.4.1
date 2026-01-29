"""
Application Layer Data Transfer Objects.
Pure data carriers for boundaries (Input/Output).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class DeviceStatusDTO:
    """
    Read-only projection of Device Status (Hot Storage).
    """

    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime] = None
    is_active: bool = True

    # Extended Meta Data
    name: Optional[str] = None
    description: Optional[str] = None

    # Material / Production Data
    material_batch: Optional[str] = None
    feeding_time: Optional[datetime] = None
    input_count: int = 0  # Placeholder for daily/shift count


@dataclass(frozen=True, slots=True)
class DeviceHistoryDTO:
    """
    Projection for device history logs (Cold Storage).
    """

    equip_code: str
    status_code: str
    timestamp: datetime
    status_name: Optional[str] = None
    end_time: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class GanttSegmentDTO:
    """
    DTO for a single Gantt chart segment.
    """

    equip_code: str
    status_code: str
    status_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0
    percent: float = 0.0
