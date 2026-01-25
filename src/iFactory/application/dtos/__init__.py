"""
Data Transfer Objects (DTOs) Package.
"""

from .device_dtos import DeviceStatusDTO
from .gantt_dto import GanttSegmentDTO  # <--- Đã tách ra file riêng
from .pagination import PaginatedResponseDTO

__all__ = [
    "DeviceStatusDTO",
    "GanttSegmentDTO",
    "PaginatedResponseDTO",
]
