# src/iFactory/presentation/viewmodels/models/__init__.py
"""
Data Models Package.

Pure immutable data containers used by ViewModels.
These are NOT ViewModels - they have no behavior, only data.

All models use:
- `frozen=True` for immutability
- `slots=True` for memory efficiency
- Type hints for IDE support

Usage:
    from .models import DeviceDisplayModel, GanttChartModel

    device = DeviceDisplayModel.empty("CMX01")
    chart = GanttChartModel.empty("CMX01")
"""

from .device_model import (
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
    MaterialInputModel,
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


# Type aliases for convenience
DeviceDict = dict[str, DeviceDisplayModel]
SegmentList = list[GanttSegmentModel]


__all__ = [
    # Device models
    "DeviceDisplayModel",
    "DeviceSelectionModel",
    "DeviceSyncStatusModel",
    "MaterialInputModel",
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
    # Type aliases
    "DeviceDict",
    "SegmentList",
]
