# src/iFactory/presentation/viewmodels/__init__.py
"""
ViewModels Package.

MVVM ViewModels for the presentation layer.

ViewModels:
- Own UI state and business logic
- Expose data via properties and signals
- Handle commands/actions from views
- Coordinate with application services

Data Models:
- Pure immutable data containers
- Used by ViewModels to represent state
- No behavior, only data

Usage:
    from iFactory.presentation.viewmodels import (
        ShellViewModel,
        DeviceListViewModel,
        GanttChartViewModel,
    )

    shell_vm = ShellViewModel(theme_service=theme_service)
    shell_vm.initialize()
"""

from .base import (
    BaseViewModel,
    AsyncViewModelMixin,
    UiState,
    UiStateType,
    ReactiveProperty,
    ComputedProperty,
    ICommand,
    RelayCommand,
    AsyncRelayCommand,
    PropertyChangeTracker,
    ValidationResult,
)

from .shell_viewmodel import ShellViewModel
from .device_viewmodel import DeviceListViewModel
from .gantt_viewmodel import GanttChartViewModel, GanttMetrics

from .models import (
    # Device
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
    MaterialInputModel,
    # Gantt
    GanttChartModel,
    GanttSegmentModel,
    GanttHourMarkModel,
    GanttStatsModel,
    GanttLoadingState,
    # Shell
    SystemStatusModel,
    ShellStateModel,
    NavigationItem,
)


__all__ = [
    # Base
    "BaseViewModel",
    "AsyncViewModelMixin",
    "UiState",
    "UiStateType",
    "ReactiveProperty",
    "ComputedProperty",
    "ICommand",
    "RelayCommand",
    "AsyncRelayCommand",
    "PropertyChangeTracker",
    "ValidationResult",
    # ViewModels
    "ShellViewModel",
    "DeviceListViewModel",
    "GanttChartViewModel",
    "GanttMetrics",
    # Models
    "DeviceDisplayModel",
    "DeviceSelectionModel",
    "DeviceSyncStatusModel",
    "MaterialInputModel",
    "GanttChartModel",
    "GanttSegmentModel",
    "GanttHourMarkModel",
    "GanttStatsModel",
    "GanttLoadingState",
    "SystemStatusModel",
    "ShellStateModel",
    "NavigationItem",
]
