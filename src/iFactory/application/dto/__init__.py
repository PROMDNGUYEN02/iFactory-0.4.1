"""
Application DTOs Package.
"""

from .device_status_dto import DeviceStatusDTO
from .gantt_dto import GanttSegmentDTO

__all__ = ["DeviceStatusDTO", "GanttSegmentDTO"]

# Type alias for collections
DeviceStatusMap = dict[str, DeviceStatusDTO]
GanttTimeline = list[GanttSegmentDTO]
