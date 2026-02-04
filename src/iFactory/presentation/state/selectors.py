# src/iFactory/presentation/state/selectors.py
"""
Memoized Selector System.

Features:
- Memoization for performance
- Composable selectors
- Derived state computation
- Type-safe returns
- Backward compatible with dict state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from .types import (
    AppState,
    DeviceSnapshot,
    FactorySummary,
    GanttSegment,
    PageId,
    SelectionState,
    SystemStatus,
    ThemeMode,
    UIState,
)

T = TypeVar("T")
S = TypeVar("S")
R = TypeVar("R")

# State can be either AppState or dict (backward compat)
State = Union[AppState, Dict[str, Any]]


# ============================================================================
# Memoization Infrastructure
# ============================================================================


@dataclass
class MemoizedSelector(Generic[T]):
    """
    Memoized selector that caches the last result.

    Only recomputes when input state reference changes.

    Usage:
        select_theme = MemoizedSelector(lambda s: s.get("theme", "light"))
        theme = select_theme(store.get_state())
    """

    selector: Callable[[State], T]
    _last_state: Optional[State] = field(default=None, repr=False, compare=False)
    _cached_result: Optional[T] = field(default=None, repr=False, compare=False)
    _cache_hits: int = field(default=0, repr=False, compare=False)
    _cache_misses: int = field(default=0, repr=False, compare=False)

    def __call__(self, state: State) -> T:
        # Identity check for memoization
        if state is self._last_state:
            self._cache_hits += 1
            return self._cached_result  # type: ignore

        self._cache_misses += 1
        self._last_state = state
        self._cached_result = self.selector(state)
        return self._cached_result

    def invalidate(self) -> None:
        """Invalidate the cache."""
        self._last_state = None
        self._cached_result = None

    @property
    def cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": self._cache_hits / max(1, self._cache_hits + self._cache_misses),
        }


def create_selector(selector_fn: Callable[[State], T]) -> MemoizedSelector[T]:
    """Create a memoized selector."""
    return MemoizedSelector(selector=selector_fn)


def create_derived_selector(
    input_selectors: List[Callable[[State], Any]],
    combiner: Callable[..., T],
) -> Callable[[State], T]:
    """
    Create a derived selector from multiple input selectors.

    Similar to reselect's createSelector.

    Usage:
        select_summary = create_derived_selector(
            [select_devices, select_data_range],
            lambda devices, range: compute_summary(devices, range)
        )
    """
    last_inputs: List[Any] = []
    cached_result: Optional[T] = None

    def derived_selector(state: State) -> T:
        nonlocal last_inputs, cached_result

        # Compute current inputs
        current_inputs = [sel(state) for sel in input_selectors]

        # Check if inputs changed
        if len(current_inputs) == len(last_inputs):
            inputs_same = all(curr is last for curr, last in zip(current_inputs, last_inputs))
            if inputs_same:
                return cached_result  # type: ignore

        # Recompute
        last_inputs = current_inputs
        cached_result = combiner(*current_inputs)
        return cached_result

    return derived_selector


# ============================================================================
# Helper: Extract value from State (handles both AppState and dict)
# ============================================================================


def _get_value(state: State, key: str, default: T = None) -> T:
    """Extract value from either AppState or dict."""
    if isinstance(state, AppState):
        return getattr(state, key, default)
    return state.get(key, default)


def _is_app_state(state: State) -> bool:
    """Check if state is AppState."""
    return isinstance(state, AppState)


# ============================================================================
# Basic Selectors
# ============================================================================


def select_theme(state: State) -> str:
    """Select current theme as string."""
    if isinstance(state, AppState):
        return state.theme.value
    return state.get("theme", "light")


def select_theme_mode(state: State) -> ThemeMode:
    """Select current theme as ThemeMode enum."""
    if isinstance(state, AppState):
        return state.theme
    return ThemeMode.from_string(state.get("theme", "light"))


def select_current_page(state: State) -> str:
    """Select current page as string."""
    if isinstance(state, AppState):
        return state.current_page.value
    return state.get("current_page", "electrode_page")


def select_current_page_id(state: State) -> PageId:
    """Select current page as PageId enum."""
    if isinstance(state, AppState):
        return state.current_page
    return PageId.from_string(state.get("current_page", "electrode_page"))


def select_sidebar_expanded(state: State) -> bool:
    """Select sidebar expansion state."""
    if isinstance(state, AppState):
        return state.ui.sidebar_expanded
    return state.get("sidebar_expanded", False)


def select_right_panel_expanded(state: State) -> bool:
    """Select right panel expansion state."""
    if isinstance(state, AppState):
        return state.ui.right_panel_expanded
    return state.get("right_panel_expanded", False)


def select_is_loading(state: State) -> bool:
    """Select loading state."""
    if isinstance(state, AppState):
        return state.ui.is_loading
    return state.get("is_loading", False)


def select_error(state: State) -> Optional[str]:
    """Select current error message."""
    if isinstance(state, AppState):
        return state.ui.error_message
    return state.get("error")


def select_ui_state(state: State) -> UIState:
    """Select full UI state."""
    if isinstance(state, AppState):
        return state.ui
    return UIState(
        sidebar_expanded=state.get("sidebar_expanded", False),
        right_panel_expanded=state.get("right_panel_expanded", False),
        is_loading=state.get("is_loading", False),
        error_message=state.get("error"),
    )


def select_data_range_days(state: State) -> int:
    """Select data range in days."""
    if isinstance(state, AppState):
        return state.data_range_days
    return state.get("data_range_days", 1)


# ============================================================================
# Device Selectors
# ============================================================================


def select_devices(state: State) -> Dict[str, Any]:
    """
    Select all devices as dict.

    Returns dict for backward compatibility.
    """
    if isinstance(state, AppState):
        return state.get_devices_dict()
    return state.get("devices", {})


def select_devices_list(state: State) -> List[DeviceSnapshot]:
    """Select devices as list of DeviceSnapshot."""
    if isinstance(state, AppState):
        return list(state.devices)

    devices_dict = state.get("devices", {})
    return [DeviceSnapshot.from_dict({**v, "device_id": k}) if isinstance(v, dict) else v for k, v in devices_dict.items()]


def select_device_by_id(state: State, device_id: str) -> Optional[Any]:
    """Select a specific device by ID."""
    if isinstance(state, AppState):
        device = state.get_device(device_id)
        return device.to_dict() if device else None

    devices = state.get("devices", {})
    return devices.get(device_id)


def select_device_snapshot_by_id(state: State, device_id: str) -> Optional[DeviceSnapshot]:
    """Select device as DeviceSnapshot."""
    if isinstance(state, AppState):
        return state.get_device(device_id)

    devices = state.get("devices", {})
    data = devices.get(device_id)
    if data is None:
        return None
    if isinstance(data, DeviceSnapshot):
        return data
    return DeviceSnapshot.from_dict({**data, "device_id": device_id})


def select_device_count(state: State) -> int:
    """Select total device count."""
    if isinstance(state, AppState):
        return len(state.devices)
    return len(state.get("devices", {}))


# ============================================================================
# Selection Selectors
# ============================================================================


def select_selected_device_id(state: State) -> Optional[str]:
    """Select the ID of the currently selected device."""
    if isinstance(state, AppState):
        return state.selection.selected_device_id
    return state.get("selected_device_id")


def select_selected_device(state: State) -> Optional[Any]:
    """Select the full device data for selected device (as dict)."""
    device_id = select_selected_device_id(state)
    if not device_id:
        return None
    return select_device_by_id(state, device_id)


def select_selected_device_snapshot(state: State) -> Optional[DeviceSnapshot]:
    """Select selected device as DeviceSnapshot."""
    device_id = select_selected_device_id(state)
    if not device_id:
        return None
    return select_device_snapshot_by_id(state, device_id)


def select_selected_device_gantt(state: State) -> Optional[Any]:
    """Select the Gantt chart ViewModel for selected device."""
    if isinstance(state, AppState):
        return state.selection.selected_gantt
    return state.get("selected_device_gantt")


def select_has_selection(state: State) -> bool:
    """Check if any device is selected."""
    return select_selected_device_id(state) is not None


def select_selection_state(state: State) -> SelectionState:
    """Select full selection state."""
    if isinstance(state, AppState):
        return state.selection
    return SelectionState(
        selected_device_id=state.get("selected_device_id"),
        selected_gantt=state.get("selected_device_gantt"),
    )


# ============================================================================
# Gantt Selectors
# ============================================================================


def select_gantt_data(state: State) -> Dict[str, List[Any]]:
    """Select gantt timeline data for all devices."""
    if isinstance(state, AppState):
        return {
            dev_id: [
                {
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "status_code": seg.status_code,
                    "status_name": seg.status_name,
                }
                for seg in segments
            ]
            for dev_id, segments in state.gantt_data
        }
    return state.get("gantt_data", {})


def select_device_gantt_by_id(state: State, device_id: str) -> List[Any]:
    """Select gantt segments for a specific device."""
    if isinstance(state, AppState):
        return list(state.get_gantt_for_device(device_id))

    gantt_data = state.get("gantt_data", {})
    return gantt_data.get(device_id, [])


def select_selected_device_gantt_segments(state: State) -> List[Any]:
    """Select gantt segments for currently selected device."""
    device_id = select_selected_device_id(state)
    if not device_id:
        return []
    return select_device_gantt_by_id(state, device_id)


# ============================================================================
# System Status Selectors
# ============================================================================


def select_system_status(state: State) -> Dict[str, Any]:
    """Select system connection status as dict."""
    if isinstance(state, AppState):
        return {
            "mssql": state.system_status.mssql_connected,
            "sqlite": state.system_status.sqlite_connected,
            "message": state.system_status.message,
        }
    return state.get("system_status", {"mssql": False, "sqlite": False, "message": ""})


def select_system_status_typed(state: State) -> SystemStatus:
    """Select system status as SystemStatus object."""
    if isinstance(state, AppState):
        return state.system_status

    status_dict = state.get("system_status", {})
    return SystemStatus(
        mssql_connected=status_dict.get("mssql", False),
        sqlite_connected=status_dict.get("sqlite", False),
        message=status_dict.get("message", ""),
    )


def select_is_mssql_connected(state: State) -> bool:
    """Check if MSSQL is connected."""
    if isinstance(state, AppState):
        return state.system_status.mssql_connected
    return state.get("system_status", {}).get("mssql", False)


def select_is_sqlite_connected(state: State) -> bool:
    """Check if SQLite is connected."""
    if isinstance(state, AppState):
        return state.system_status.sqlite_connected
    return state.get("system_status", {}).get("sqlite", False)


# ============================================================================
# Computed/Derived Selectors
# ============================================================================


def select_factory_summary(state: State) -> Dict[str, Any]:
    """
    Compute factory summary statistics.

    Returns dict for backward compatibility.
    """
    if isinstance(state, AppState):
        summary = state.compute_factory_summary()
        return {
            "total_output": summary.total_output,
            "total_input": summary.total_input,
            "yield_rate": summary.yield_rate,
            "device_count": summary.total_devices,
            "running_count": summary.running_count,
            "stopped_count": summary.stopped_count,
            "alarm_count": summary.alarm_count,
        }

    devices = state.get("devices", {})
    if not devices:
        return {
            "total_output": 0,
            "total_input": 0,
            "yield_rate": 0.0,
            "device_count": 0,
            "running_count": 0,
            "stopped_count": 0,
            "alarm_count": 0,
        }

    total_input = 0
    total_output = 0
    running_count = 0
    stopped_count = 0
    alarm_count = 0

    for device in devices.values():
        if isinstance(device, dict):
            total_input += device.get("input_count", 0) or 0
            total_output += device.get("output_count", 0) or 0
            status_code = device.get("status_code", 0)
        else:
            total_input += getattr(device, "input_count", 0) or 0
            total_output += getattr(device, "output_count", 0) or 0
            status_code = getattr(device, "status_code", 0)

        if status_code == 1:
            running_count += 1
        elif status_code == 3:
            stopped_count += 1
        elif status_code == 5:
            alarm_count += 1

    yield_rate = (total_output / total_input * 100) if total_input > 0 else 0.0

    return {
        "total_output": total_output,
        "total_input": total_input,
        "yield_rate": round(yield_rate, 2),
        "device_count": len(devices),
        "running_count": running_count,
        "stopped_count": stopped_count,
        "alarm_count": alarm_count,
    }


def select_factory_summary_typed(state: State) -> FactorySummary:
    """Compute factory summary as FactorySummary object."""
    if isinstance(state, AppState):
        return state.compute_factory_summary()

    # Compute from dict state
    devices = state.get("devices", {})
    if not devices:
        return FactorySummary()

    running = stopped = alarm = idle = 0
    total_input = total_output = total_ng = 0

    for device in devices.values():
        if isinstance(device, dict):
            total_input += device.get("input_count", 0) or 0
            total_output += device.get("output_count", 0) or 0
            total_ng += device.get("ng_count", 0) or 0
            status_code = device.get("status_code", 0)
        else:
            total_input += getattr(device, "input_count", 0) or 0
            total_output += getattr(device, "output_count", 0) or 0
            total_ng += getattr(device, "ng_count", 0) or 0
            status_code = getattr(device, "status_code", 0)

        if status_code == 1:
            running += 1
        elif status_code == 3:
            stopped += 1
        elif status_code == 5:
            alarm += 1
        else:
            idle += 1

    return FactorySummary(
        total_devices=len(devices),
        running_count=running,
        stopped_count=stopped,
        alarm_count=alarm,
        idle_count=idle,
        total_input=total_input,
        total_output=total_output,
        total_ng=total_ng,
    )


# ============================================================================
# Page Device Selectors
# ============================================================================


def select_page_devices(state: State) -> Dict[str, List[str]]:
    """Select page device mappings."""
    if isinstance(state, AppState):
        return {page: list(devices) for page, devices in state.page_devices}
    return state.get("page_devices", {})


def select_devices_for_page(state: State, page: str) -> List[str]:
    """Select device IDs for a specific page."""
    if isinstance(state, AppState):
        return list(state.get_page_device_ids(page))

    page_devices = state.get("page_devices", {})
    return page_devices.get(page, [])


def select_current_page_devices(state: State) -> List[str]:
    """Select device IDs for current page."""
    page = select_current_page(state)
    return select_devices_for_page(state, page)


# ============================================================================
# Memoized Selector Instances
# ============================================================================


# Pre-created memoized selectors for common operations
memoized_select_theme = create_selector(select_theme)
memoized_select_devices = create_selector(select_devices)
memoized_select_device_count = create_selector(select_device_count)
memoized_select_selected_device_id = create_selector(select_selected_device_id)
memoized_select_factory_summary = create_selector(select_factory_summary)
memoized_select_system_status = create_selector(select_system_status)


# Derived selectors
select_running_devices = create_derived_selector([select_devices_list], lambda devices: [d for d in devices if d.is_running])

select_alarm_devices = create_derived_selector([select_devices_list], lambda devices: [d for d in devices if d.is_alarm])

select_devices_by_status = create_derived_selector(
    [select_devices_list],
    lambda devices: {
        "running": [d for d in devices if d.is_running],
        "stopped": [d for d in devices if d.is_stopped],
        "alarm": [d for d in devices if d.is_alarm],
        "other": [d for d in devices if not (d.is_running or d.is_stopped or d.is_alarm)],
    },
)


# ============================================================================
# Selector Combinators
# ============================================================================


def with_default(selector: Callable[[State], Optional[T]], default: T) -> Callable[[State], T]:
    """Wrap selector to provide default value if None."""

    def wrapped(state: State) -> T:
        result = selector(state)
        return result if result is not None else default

    return wrapped


def map_selector(
    selector: Callable[[State], List[T]],
    mapper: Callable[[T], R],
) -> Callable[[State], List[R]]:
    """Map over selector results."""

    def mapped(state: State) -> List[R]:
        return [mapper(item) for item in selector(state)]

    return mapped


def filter_selector(
    selector: Callable[[State], List[T]],
    predicate: Callable[[T], bool],
) -> Callable[[State], List[T]]:
    """Filter selector results."""

    def filtered(state: State) -> List[T]:
        return [item for item in selector(state) if predicate(item)]

    return filtered


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Memoization
    "MemoizedSelector",
    "create_selector",
    "create_derived_selector",
    # Basic selectors
    "select_theme",
    "select_theme_mode",
    "select_current_page",
    "select_current_page_id",
    "select_sidebar_expanded",
    "select_right_panel_expanded",
    "select_is_loading",
    "select_error",
    "select_ui_state",
    "select_data_range_days",
    # Device selectors
    "select_devices",
    "select_devices_list",
    "select_device_by_id",
    "select_device_snapshot_by_id",
    "select_device_count",
    # Selection selectors
    "select_selected_device_id",
    "select_selected_device",
    "select_selected_device_snapshot",
    "select_selected_device_gantt",
    "select_has_selection",
    "select_selection_state",
    # Gantt selectors
    "select_gantt_data",
    "select_device_gantt_by_id",
    "select_selected_device_gantt_segments",
    # System status selectors
    "select_system_status",
    "select_system_status_typed",
    "select_is_mssql_connected",
    "select_is_sqlite_connected",
    # Computed selectors
    "select_factory_summary",
    "select_factory_summary_typed",
    # Page device selectors
    "select_page_devices",
    "select_devices_for_page",
    "select_current_page_devices",
    # Memoized instances
    "memoized_select_theme",
    "memoized_select_devices",
    "memoized_select_device_count",
    "memoized_select_selected_device_id",
    "memoized_select_factory_summary",
    "memoized_select_system_status",
    # Derived selectors
    "select_running_devices",
    "select_alarm_devices",
    "select_devices_by_status",
    # Combinators
    "with_default",
    "map_selector",
    "filter_selector",
]
