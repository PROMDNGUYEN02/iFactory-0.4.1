"""
State reducers for the application.
Reducers are pure functions that transform state based on actions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .store import Action
from .models import (
    ApplicationState,
    GlobalUIState,
    DeviceCollectionState,
    GanttChartState,
    RightPanelState,
    LoadingState,
    DeviceUIState,
    GanttSegmentState,
)

logger = logging.getLogger(__name__)


class GlobalUIReducer:
    """Reducer for global UI state."""
    
    @staticmethod
    def reduce(state: GlobalUIState, action: Action) -> GlobalUIState:
        """Reduce global UI state based on action."""
        action_type = action.type.lower()
        
        if "theme" in action_type:
            return state.with_theme(action.payload or "light")
        
        elif "page" in action_type:
            return state.with_page(action.payload or "dashboard")
        
        elif "loading_start" in action_type:
            return state.with_loading(1)
        
        elif "loading_end" in action_type:
            return state.with_loading(-1)
        
        return state


class DeviceCollectionReducer:
    """Reducer for device collection state."""
    
    @staticmethod
    def reduce(state: DeviceCollectionState, action: Action) -> DeviceCollectionState:
        """Reduce device collection state based on action."""
        action_type = action.type.lower()
        
        if "device_loading_start" in action_type:
            return state.with_loading(LoadingState.LOADING)
        
        elif "device_loading_end" in action_type:
            return state.with_loading(LoadingState.SUCCESS)
        
        elif "device_error" in action_type:
            return state.with_error(str(action.payload))
        
        elif "device_update" in action_type:
            return DeviceCollectionReducer._handle_device_update(state, action.payload)
        
        elif "device_batch_update" in action_type:
            return DeviceCollectionReducer._handle_batch_update(state, action.payload)
        
        return state
    
    @staticmethod
    def _handle_device_update(
        state: DeviceCollectionState,
        payload: Dict[str, Any]
    ) -> DeviceCollectionState:
        """Handle single device update."""
        if not payload or "device_id" not in payload:
            return state
        
        device_id = payload["device_id"]
        existing = state.devices.get(device_id)
        
        if existing:
            device_state = existing
        else:
            device_state = DeviceUIState(
                device_id=device_id,
                device_name=payload.get("device_name", device_id)
            )
        
        if "status_code" in payload:
            device_state = device_state.with_status(
                payload["status_code"],
                payload.get("status_display", "Unknown"),
                payload.get("status_color", "#808080")
            )
        
        if "input_data" in payload or "output_data" in payload:
            device_state = device_state.with_io_data(
                payload.get("input_data"),
                payload.get("output_data")
            )
        
        return state.with_device(device_state)
    
    @staticmethod
    def _handle_batch_update(
        state: DeviceCollectionState,
        payload: List[Dict[str, Any]]
    ) -> DeviceCollectionState:
        """Handle batch device update."""
        if not payload or not isinstance(payload, list):
            return state
        
        devices = state.devices.copy()
        
        for item in payload:
            if not item or "device_id" not in item:
                continue
            
            device_id = item["device_id"]
            existing = devices.get(device_id)
            
            if existing:
                device_state = existing
            else:
                device_state = DeviceUIState(
                    device_id=device_id,
                    device_name=item.get("device_name", device_id)
                )
            
            if "status_code" in item:
                device_state = device_state.with_status(
                    item["status_code"],
                    item.get("status_display", "Unknown"),
                    item.get("status_color", "#808080")
                )
            
            if "input_data" in item or "output_data" in item:
                device_state = device_state.with_io_data(
                    item.get("input_data"),
                    item.get("output_data")
                )
            
            devices[device_id] = device_state
        
        return DeviceCollectionState(
            devices=devices,
            selected_devices=state.selected_devices,
            loading_state=LoadingState.SUCCESS,
            error_message=None,
            last_refresh=state.last_refresh,
        )


class GanttChartReducer:
    """Reducer for Gantt chart state."""
    
    @staticmethod
    def reduce(
        charts: Dict[str, GanttChartState],
        action: Action
    ) -> Dict[str, GanttChartState]:
        """Reduce Gantt charts state based on action."""
        action_type = action.type.lower()
        
        if not isinstance(action.payload, dict) or "device_id" not in action.payload:
            return charts
        
        device_id = action.payload["device_id"]
        existing = charts.get(device_id)
        
        if not existing:
            existing = GanttChartState(device_id=device_id)
        
        if "gantt_loading_start" in action_type:
            updated = existing.with_loading(LoadingState.LOADING)
        
        elif "gantt_loading_end" in action_type:
            updated = existing.with_loading(LoadingState.SUCCESS)
        
        elif "gantt_error" in action_type:
            updated = existing.with_error(str(action.payload.get("error", "Unknown error")))
        
        elif "gantt_update" in action_type:
            updated = GanttChartReducer._handle_gantt_update(
                existing,
                action.payload
            )
        
        else:
            return charts
        
        result = charts.copy()
        result[device_id] = updated
        return result
    
    @staticmethod
    def _handle_gantt_update(
        state: GanttChartState,
        payload: Dict[str, Any]
    ) -> GanttChartState:
        """Handle Gantt chart update."""
        segments = payload.get("segments", [])
        
        segment_states = []
        for seg in segments:
            if isinstance(seg, GanttSegmentState):
                segment_states.append(seg)
            elif isinstance(seg, dict):
                segment_states.append(GanttSegmentState(
                    device_id=payload["device_id"],
                    segment_id=seg.get("segment_id", ""),
                    start_time=seg.get("start_time"),
                    end_time=seg.get("end_time"),
                    status_code=seg.get("status_code", "unknown"),
                    status_display=seg.get("status_display", "Unknown"),
                    status_color=seg.get("status_color", "#808080")
                ))
        
        return state.with_segments(
            segments=segment_states,
            start_time=payload.get("start_time"),
            end_time=payload.get("end_time")
        )


class RightPanelReducer:
    """Reducer for right panel state."""
    
    @staticmethod
    def reduce(state: RightPanelState, action: Action) -> RightPanelState:
        """Reduce right panel state based on action."""
        action_type = action.type.lower()
        
        if "panel_visibility" in action_type:
            return state.with_visibility(action.payload or False)
        
        elif "panel_show_device" in action_type:
            if isinstance(action.payload, dict):
                return state.with_device(
                    device_id=action.payload.get("device_id", ""),
                    device_name=action.payload.get("device_name", ""),
                    panel_type=action.payload.get("panel_type", "history")
                )
        
        elif "panel_loading_end" in action_type:
            return state.with_data(action.payload)
        
        elif "panel_error" in action_type:
            return state.with_error(str(action.payload))
        
        return state


class ApplicationReducer:
    """Root reducer that delegates to child reducers."""
    
    @staticmethod
    def reduce(state: ApplicationState, action: Action) -> ApplicationState:
        """Reduce application state based on action."""
        global_state = GlobalUIReducer.reduce(state.global_state, action)
        devices = DeviceCollectionReducer.reduce(state.devices, action)
        gantt_charts = GanttChartReducer.reduce(state.gantt_charts, action)
        right_panel = RightPanelReducer.reduce(state.right_panel, action)
        
        return ApplicationState(
            global_state=global_state,
            devices=devices,
            gantt_charts=gantt_charts,
            right_panel=right_panel,
        )


def create_reducer_map() -> Dict[str, Any]:
    """
    Create reducer map for Store initialization.
    
    Returns:
        Dictionary mapping state slice names to reducers
    """
    return {
        "application_state": ApplicationReducer.reduce,
    }


__all__ = [
    'GlobalUIReducer',
    'DeviceCollectionReducer',
    'GanttChartReducer',
    'RightPanelReducer',
    'ApplicationReducer',
    'create_reducer_map',
]
