"""
Gantt chart configuration.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

__all__ = ["GanttConfig", "FrameMetadata"]


@dataclass(slots=True)
class GanttConfig:
    """
    Gantt chart configuration.

    Controls display and behavior of Gantt strip widgets.
    """

    show_summary: bool = False
    show_axis: bool = True
    show_now_line: bool = True
    show_segment_labels: bool = True
    min_height: int = 38
    default_range_hours: int = 24
    max_segments: int = 1000
    cache_results: bool = True
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    @classmethod
    def for_dashboard(cls) -> "GanttConfig":
        """Create config optimized for dashboard display."""
        return cls(
            show_summary=False, show_axis=True, min_height=38, default_range_hours=24
        )

    @classmethod
    def for_detail_view(cls) -> "GanttConfig":
        """Create config for detailed Gantt view."""
        return cls(
            show_summary=True,
            show_axis=True,
            show_segment_labels=True,
            min_height=60,
            default_range_hours=24,
        )


@dataclass
class FrameMetadata:
    """
    Metadata for a registered Gantt frame.

    Tracks state and loading information for each frame.
    """

    frame: Any
    widget: Any
    device_code: str = ""
    last_loaded: Optional[datetime] = None
    segment_count: int = 0
    loading: bool = False
    error_count: int = 0

    @property
    def has_data(self) -> bool:
        """Check if frame has loaded data."""
        return self.segment_count > 0

    @property
    def is_stale(self) -> bool:
        """Check if data is stale (more than 5 minutes old)."""
        if self.last_loaded is None:
            return True
        from datetime import timedelta

        return datetime.now() - self.last_loaded > timedelta(minutes=5)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for debugging."""
        return {
            "device_code": self.device_code,
            "segment_count": self.segment_count,
            "loading": self.loading,
            "error_count": self.error_count,
            "last_loaded": self.last_loaded.isoformat() if self.last_loaded else None,
            "is_stale": self.is_stale,
        }
