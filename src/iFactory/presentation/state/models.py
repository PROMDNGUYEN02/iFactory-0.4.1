"""
Domain-specific state models for the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class LoadingState(Enum):
    """Loading state enumeration."""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"


class DeviceStatus(Enum):
    """Device status enumeration."""
    UNKNOWN = "unknown"
    RUNNING = "running"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class DeviceUIState:
    """
    UI state for a single device.
    
    Immutable - create new instances for updates.
    """
    device_id: str
    device_name: str
    status_code: str = "0"
    status_display: str = "Unknown"
    status_color: str = "#808080"
    is_running: bool = False
    is_attention_required: bool = False
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Input/output data
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    
    # UI interaction state
    is_selected: bool = False
    is_hovered: bool = False
    
    def with_status(
        self,
        status_code: str,
        status_display: str,
        status_color: str
    ) -> 'DeviceUIState':
        """Create new state with updated status."""
        return DeviceUIState(
            device_id=self.device_id,
            device_name=self.device_name,
            status_code=status_code,
            status_display=status_display,
            status_color=status_color,
            is_running=status_code in ["1", "2", "3"],
            is_attention_required=status_code in ["4", "5", "6"],
            last_updated=datetime.now(),
            input_data=self.input_data,
            output_data=self.output_data,
            is_selected=self.is_selected,
            is_hovered=self.is_hovered,
        )
    
    def with_io_data(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None
    ) -> 'DeviceUIState':
        """Create new state with updated I/O data."""
        return DeviceUIState(
            device_id=self.device_id,
            device_name=self.device_name,
            status_code=self.status_code,
            status_display=self.status_display,
            status_color=self.status_color,
            is_running=self.is_running,
            is_attention_required=self.is_attention_required,
            last_updated=self.last_updated,
            input_data=input_data or self.input_data,
            output_data=output_data or self.output_data,
            is_selected=self.is_selected,
            is_hovered=self.is_hovered,
        )
    
    def with_selection(self, is_selected: bool) -> 'DeviceUIState':
        """Create new state with updated selection."""
        return DeviceUIState(
            device_id=self.device_id,
            device_name=self.device_name,
            status_code=self.status_code,
            status_display=self.status_display,
            status_color=self.status_color,
            is_running=self.is_running,
            is_attention_required=self.is_attention_required,
            last_updated=self.last_updated,
            input_data=self.input_data,
            output_data=self.output_data,
            is_selected=is_selected,
            is_hovered=self.is_hovered,
        )


@dataclass
class DeviceCollectionState:
    """
    UI state for a collection of devices.
    """
    devices: Dict[str, DeviceUIState] = field(default_factory=dict)
    selected_devices: Set[str] = field(default_factory=set)
    loading_state: LoadingState = LoadingState.IDLE
    error_message: Optional[str] = None
    last_refresh: Optional[datetime] = None
    
    def with_device(self, device_state: DeviceUIState) -> 'DeviceCollectionState':
        """Create new state with updated device."""
        new_devices = self.devices.copy()
        new_devices[device_state.device_id] = device_state
        return DeviceCollectionState(
            devices=new_devices,
            selected_devices=self.selected_devices,
            loading_state=self.loading_state,
            error_message=self.error_message,
            last_refresh=datetime.now(),
        )
    
    def with_loading(self, loading_state: LoadingState) -> 'DeviceCollectionState':
        """Create new state with updated loading state."""
        return DeviceCollectionState(
            devices=self.devices,
            selected_devices=self.selected_devices,
            loading_state=loading_state,
            error_message=self.error_message,
            last_refresh=self.last_refresh,
        )
    
    def with_error(self, error_message: str) -> 'DeviceCollectionState':
        """Create new state with error."""
        return DeviceCollectionState(
            devices=self.devices,
            selected_devices=self.selected_devices,
            loading_state=LoadingState.ERROR,
            error_message=error_message,
            last_refresh=self.last_refresh,
        )


@dataclass
class GanttSegmentState:
    """
    UI state for a single Gantt segment.
    """
    device_id: str
    segment_id: str
    start_time: datetime
    end_time: datetime
    status_code: str
    status_display: str
    status_color: str
    
    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for backward compatibility."""
        return (self.start_time, self.end_time, self.status_code)


@dataclass
class GanttChartState:
    """
    UI state for a Gantt chart.
    """
    device_id: str
    segments: List[GanttSegmentState] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    loading_state: LoadingState = LoadingState.IDLE
    error_message: Optional[str] = None
    
    def with_segments(
        self,
        segments: List[GanttSegmentState],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> 'GanttChartState':
        """Create new state with updated segments."""
        return GanttChartState(
            device_id=self.device_id,
            segments=segments,
            start_time=start_time or self.start_time,
            end_time=end_time or self.end_time,
            loading_state=LoadingState.SUCCESS,
            error_message=None,
        )
    
    def with_loading(self, loading_state: LoadingState) -> 'GanttChartState':
        """Create new state with updated loading state."""
        return GanttChartState(
            device_id=self.device_id,
            segments=self.segments,
            start_time=self.start_time,
            end_time=self.end_time,
            loading_state=loading_state,
            error_message=self.error_message,
        )
    
    def with_error(self, error_message: str) -> 'GanttChartState':
        """Create new state with error."""
        return GanttChartState(
            device_id=self.device_id,
            segments=self.segments,
            start_time=self.start_time,
            end_time=self.end_time,
            loading_state=LoadingState.ERROR,
            error_message=error_message,
        )


@dataclass
class RightPanelState:
    """
    UI state for the right panel.
    """
    visible: bool = False
    panel_type: str = "history"  # history, details, settings
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    data: Any = None
    loading_state: LoadingState = LoadingState.IDLE
    error_message: Optional[str] = None
    
    def with_visibility(self, visible: bool) -> 'RightPanelState':
        """Create new state with updated visibility."""
        return RightPanelState(
            visible=visible,
            panel_type=self.panel_type,
            device_id=self.device_id,
            device_name=self.device_name,
            data=self.data,
            loading_state=self.loading_state,
            error_message=self.error_message,
        )
    
    def with_device(
        self,
        device_id: str,
        device_name: str,
        panel_type: str = "history"
    ) -> 'RightPanelState':
        """Create new state with updated device."""
        return RightPanelState(
            visible=self.visible,
            panel_type=panel_type,
            device_id=device_id,
            device_name=device_name,
            data=self.data,
            loading_state=LoadingState.LOADING,
            error_message=None,
        )
    
    def with_data(self, data: Any) -> 'RightPanelState':
        """Create new state with updated data."""
        return RightPanelState(
            visible=self.visible,
            panel_type=self.panel_type,
            device_id=self.device_id,
            device_name=self.device_name,
            data=data,
            loading_state=LoadingState.SUCCESS,
            error_message=None,
        )
    
    def with_error(self, error_message: str) -> 'RightPanelState':
        """Create new state with error."""
        return RightPanelState(
            visible=self.visible,
            panel_type=self.panel_type,
            device_id=self.device_id,
            device_name=self.device_name,
            data=self.data,
            loading_state=LoadingState.ERROR,
            error_message=error_message,
        )


@dataclass
class GlobalUIState:
    """
    Global UI state.
    """
    theme: str = "light"
    current_page: str = "dashboard"
    loading_count: int = 0
    is_loading: bool = False
    
    def with_theme(self, theme: str) -> 'GlobalUIState':
        """Create new state with updated theme."""
        return GlobalUIState(
            theme=theme,
            current_page=self.current_page,
            loading_count=self.loading_count,
            is_loading=self.is_loading,
        )
    
    def with_page(self, page: str) -> 'GlobalUIState':
        """Create new state with updated page."""
        return GlobalUIState(
            theme=self.theme,
            current_page=page,
            loading_count=self.loading_count,
            is_loading=self.is_loading,
        )
    
    def with_loading(self, delta: int) -> 'GlobalUIState':
        """Create new state with updated loading count."""
        new_count = max(0, self.loading_count + delta)
        return GlobalUIState(
            theme=self.theme,
            current_page=self.current_page,
            loading_count=new_count,
            is_loading=new_count > 0,
        )


@dataclass
class ApplicationState:
    """
    Root application state.
    
    Contains all UI state slices in a single immutable object.
    """
    global_state: GlobalUIState = field(default_factory=GlobalUIState)
    devices: DeviceCollectionState = field(default_factory=DeviceCollectionState)
    gantt_charts: Dict[str, GanttChartState] = field(default_factory=dict)
    right_panel: RightPanelState = field(default_factory=RightPanelState)
    
    def with_global(self, global_state: GlobalUIState) -> 'ApplicationState':
        """Create new state with updated global state."""
        return ApplicationState(
            global_state=global_state,
            devices=self.devices,
            gantt_charts=self.gantt_charts,
            right_panel=self.right_panel,
        )
    
    def with_devices(self, devices: DeviceCollectionState) -> 'ApplicationState':
        """Create new state with updated devices."""
        return ApplicationState(
            global_state=self.global_state,
            devices=devices,
            gantt_charts=self.gantt_charts,
            right_panel=self.right_panel,
        )
    
    def with_gantt_chart(self, device_id: str, chart: GanttChartState) -> 'ApplicationState':
        """Create new state with updated Gantt chart."""
        new_charts = self.gantt_charts.copy()
        new_charts[device_id] = chart
        return ApplicationState(
            global_state=self.global_state,
            devices=self.devices,
            gantt_charts=new_charts,
            right_panel=self.right_panel,
        )
    
    def with_right_panel(self, right_panel: RightPanelState) -> 'ApplicationState':
        """Create new state with updated right panel."""
        return ApplicationState(
            global_state=self.global_state,
            devices=self.devices,
            gantt_charts=self.gantt_charts,
            right_panel=right_panel,
        )


__all__ = [
    'LoadingState',
    'DeviceStatus',
    'DeviceUIState',
    'DeviceCollectionState',
    'GanttSegmentState',
    'GanttChartState',
    'RightPanelState',
    'GlobalUIState',
    'ApplicationState',
]
