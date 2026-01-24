"""
Gantt segment DTO - Data transfer object for Gantt chart rendering.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any

__all__ = ["GanttSegmentDTO"]


@dataclass(frozen=True, slots=True)
class GanttSegmentDTO:
    """
    Immutable Gantt segment DTO for chart rendering.
    """

    start_time: datetime
    end_time: datetime
    status_code: str
    status_name: str
    status_color: str

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0

    def to_dict(self) -> dict[str, Any]:
        """Convert the DTO to a dictionary suitable for generic JSON serialization."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status_code": self.status_code,
            "status_name": self.status_name,
            "status_color": self.status_color,
            "duration_seconds": self.duration_seconds,
            "duration_minutes": self.duration_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GanttSegmentDTO":
        """Reconstruct DTO from dict (used for Cache deserialization)."""
        return cls(
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            status_code=data["status_code"],
            status_name=data["status_name"],
            status_color=data["status_color"],
        )
