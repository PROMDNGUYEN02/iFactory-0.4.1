"""
ViewModels Package.

MVVM ViewModels that:
- Own UI state
- Expose reactive signals
- Orchestrate Use Cases
- Contain zero business rules

Structure:
- viewmodels/base.py - Base classes and UiState
- viewmodels/models/ - Pure data models (immutable)
- viewmodels/*_viewmodel.py - Actual ViewModels with signals
"""

# Base classes
from .base import (
    BaseViewModel,
    UiState,
    UiStateType,
    AsyncViewModelMixin,
)

# ViewModels
from .device_viewmodel import DeviceListViewModel
from .gantt_viewmodel import GanttChartViewModel, GanttFetchWorker
from .shell_viewmodel import ShellViewModel

# Data models (re-export for convenience)
from .models import (
    # Device models
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
    # Gantt models
    GanttSegmentModel,
    GanttHourMarkModel,
    GanttStatsModel,
    GanttChartModel,
    GanttLoadingState,
    STATUS_GRADIENTS,
    STATUS_NAMES,
    # Shell models
    SystemStatusModel,
    ShellStateModel,
    NavigationItem,
)


__all__ = [
    # Base
    "BaseViewModel",
    "UiState",
    "UiStateType",
    "AsyncViewModelMixin",
    # ViewModels
    "DeviceListViewModel",
    "GanttChartViewModel",
    "GanttFetchWorker",
    "ShellViewModel",
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
