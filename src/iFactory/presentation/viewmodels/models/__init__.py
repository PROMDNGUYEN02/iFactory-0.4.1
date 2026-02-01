"""
Data Models Package.

Pure immutable data containers used by ViewModels.
These are NOT ViewModels - they have no behavior, only data.
"""

from .device_model import (
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
)

from .gantt_model import (
    GanttSegmentModel,
    GanttHourMarkModel,
    GanttStatsModel,
    GanttChartModel,
    GanttLoadingState,
    STATUS_GRADIENTS,
    STATUS_NAMES,
)

from .shell_model import (
    SystemStatusModel,
    ShellStateModel,
    NavigationItem,
)

__all__ = [
    # Device models
    "DeviceDisplayModel",
    "DeviceSelectionModel",
    "DeviceSyncStatusModel",
    # Gantt models
    "GanttSegmentModel",
    "GanttHourMarkModel",
    "GanttStatsModel",
    "GanttChartModel",
    "GanttLoadingState",
    "STATUS_GRADIENTS",
    "STATUS_NAMES",
    # Shell models
    "SystemStatusModel",
    "ShellStateModel",
    "NavigationItem",
]
