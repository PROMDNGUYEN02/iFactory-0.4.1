"""
Application Layer DTOs for Device data.
Read-only projections with NO UI logic (no colors, no translations).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class DeviceStatusDTO:
    """
    Read-only projection of Device Status.
    Contains NO UI logic (no colors, no translations).
    Used for Hot Storage queries (latest state).
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
    """
    Projection for device history logs.
    Used for Cold Storage queries (history).
    """

    equip_code: str
    status_code: str
    timestamp: datetime
    status_name: Optional[str] = None
    end_time: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class StatusPeriodDTO:
    """
    DTO for status period (Gantt segment).
    Used for Cold Storage timeline queries.
    """

    id: Optional[str]
    device_code: str
    status_code: str
    status_name: str
    start_time: datetime
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    @property
    def is_open(self) -> bool:
        """Check if period is still open (no end time)."""
        return self.end_time is None


@dataclass(frozen=True, slots=True)
class MaterialInputDTO:
    """
    DTO for material input.
    Used for both Hot (latest) and Cold (history) storage.
    """

    equipment_code: str
    material_batch: str
    feeding_time: datetime
    recorded_at: Optional[datetime] = None


@dataclass(frozen=True, slots=True)
class GanttSegmentDTO:
    """
    DTO for a single Gantt chart segment.
    Pre-calculated for rendering.
    """

    equip_code: str
    status_code: str
    status_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    percent: float  # Percentage of total timeline


__all__ = [
    "DeviceStatusDTO",
    "DeviceHistoryDTO",
    "StatusPeriodDTO",
    "MaterialInputDTO",
    "GanttSegmentDTO",
]
