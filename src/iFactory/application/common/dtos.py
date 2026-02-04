# src/iFactory/application/common/dtos.py
"""
Application Layer Data Transfer Objects.

DTOs are pure data carriers used at application boundaries.
They are immutable and contain no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================================
# Device DTOs
# ============================================================================


@dataclass(frozen=True, slots=True)
class DeviceStatusDTO:
    """
    Read-only projection of Device Status.

    Used for dashboard displays and status lists.
    """

    equip_code: str
    status_code: str
    status_name: str
    last_update: Optional[datetime] = None
    is_active: bool = True

    # Extended metadata
    name: Optional[str] = None
    description: Optional[str] = None

    # Material/Production data
    material_batch: Optional[str] = None
    feeding_time: Optional[datetime] = None
    input_count: int = 0

    # Availability data
    availability: float = 0.0  # Percentage (0-100)
    run_time_seconds: float = 0.0
    total_time_seconds: float = 0.0

    # Sync metadata
    sync_source: Optional[str] = None
    synced_at: Optional[datetime] = None

    @property
    def availability_formatted(self) -> str:
        """Get formatted availability string."""
        return f"{self.availability:.1f}%"

    @property
    def run_time_formatted(self) -> str:
        """Get formatted run time (HH:MM:SS)."""
        hours = int(self.run_time_seconds // 3600)
        minutes = int((self.run_time_seconds % 3600) // 60)
        seconds = int(self.run_time_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "equip_code": self.equip_code,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "is_active": self.is_active,
            "name": self.name,
            "availability": self.availability,
            "run_time_seconds": self.run_time_seconds,
        }


@dataclass(frozen=True, slots=True)
class DeviceDetailDTO(DeviceStatusDTO):
    """
    Extended device information for detail views.
    """

    reason_code: Optional[str] = None
    alarm_count_today: int = 0
    downtime_seconds_today: float = 0.0

    # History summary
    status_changes_today: int = 0
    last_alarm_time: Optional[datetime] = None


# ============================================================================
# History DTOs
# ============================================================================


@dataclass(frozen=True, slots=True)
class DeviceHistoryDTO:
    """
    Projection for device history logs.
    """

    equip_code: str
    status_code: str
    timestamp: datetime
    status_name: Optional[str] = None
    end_time: Optional[datetime] = None
    reason_code: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration if end_time is set."""
        if self.end_time:
            return (self.end_time - self.timestamp).total_seconds()
        return None

    @property
    def is_ongoing(self) -> bool:
        """Check if this is an ongoing period."""
        return self.end_time is None


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
    percent: float = 0.0  # Percentage of total time range

    # Visual hints
    color: Optional[str] = None
    is_highlighted: bool = False

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "equip_code": self.equip_code,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "percent": self.percent,
            "color": self.color,
        }


@dataclass(frozen=True, slots=True)
class TimelineDTO:
    """
    Complete timeline for a device.
    """

    equip_code: str
    start_time: datetime
    end_time: datetime
    segments: tuple[GanttSegmentDTO, ...] = field(default_factory=tuple)
    total_duration_seconds: float = 0.0

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    def get_status_summary(self) -> Dict[str, float]:
        """Get time spent in each status."""
        summary: Dict[str, float] = {}
        for segment in self.segments:
            key = segment.status_name
            summary[key] = summary.get(key, 0.0) + segment.duration_seconds
        return summary


# ============================================================================
# Sync DTOs
# ============================================================================


@dataclass(frozen=True, slots=True)
class SyncResultDTO:
    """
    Result of a sync operation.
    """

    success: bool
    devices_synced: int = 0
    records_synced: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    error_message: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error_message is not None


@dataclass(frozen=True, slots=True)
class SyncStatusDTO:
    """
    Current sync status.
    """

    is_syncing: bool = False
    last_sync: Optional[datetime] = None
    last_error: Optional[str] = None
    devices_tracked: int = 0
    sync_interval_seconds: int = 3


# ============================================================================
# Statistics DTOs
# ============================================================================


@dataclass(frozen=True, slots=True)
class DeviceStatsDTO:
    """
    Statistics for a device.
    """

    equip_code: str
    period_start: datetime
    period_end: datetime

    # Time breakdown
    run_time_seconds: float = 0.0
    stop_time_seconds: float = 0.0
    alarm_time_seconds: float = 0.0
    maintenance_time_seconds: float = 0.0
    unknown_time_seconds: float = 0.0

    # Counts
    status_changes: int = 0
    alarm_count: int = 0

    # Calculated
    availability: float = 0.0

    @property
    def total_time_seconds(self) -> float:
        return (self.period_end - self.period_start).total_seconds()


@dataclass(frozen=True, slots=True)
class DashboardSummaryDTO:
    """
    Summary for dashboard display.
    """

    total_devices: int = 0
    running_count: int = 0
    stopped_count: int = 0
    alarm_count: int = 0
    maintenance_count: int = 0
    unknown_count: int = 0

    overall_availability: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def active_count(self) -> int:
        return self.running_count + self.stopped_count

    @property
    def problem_count(self) -> int:
        return self.alarm_count + self.unknown_count


# ============================================================================
# Pagination DTOs
# ============================================================================


@dataclass(frozen=True, slots=True)
class PagedResultDTO:
    """
    Generic paged result container.
    """

    items: tuple[Any, ...] = field(default_factory=tuple)
    total_count: int = 0
    page: int = 1
    page_size: int = 50

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total_count + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


__all__ = [
    # Device
    "DeviceStatusDTO",
    "DeviceDetailDTO",
    # History
    "DeviceHistoryDTO",
    "GanttSegmentDTO",
    "TimelineDTO",
    # Sync
    "SyncResultDTO",
    "SyncStatusDTO",
    # Statistics
    "DeviceStatsDTO",
    "DashboardSummaryDTO",
    # Pagination
    "PagedResultDTO",
]
