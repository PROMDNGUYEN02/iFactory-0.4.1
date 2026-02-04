# src/iFactory/presentation/state/__init__.py
"""
State Management Module.

Provides Redux-like state management with:
- Typed state definitions
- Immutable state updates
- Action creators
- Memoized selectors
- Middleware support
- Optional time-travel debugging
"""

from .types import (
    # Enums
    ThemeMode,
    PageId,
    ConnectionStatus,
    # Value Objects
    SystemStatus,
    DeviceSnapshot,
    GanttSegment,
    FactorySummary,
    UIState,
    SelectionState,
    # Root State
    AppState,
    create_initial_state,
    INITIAL_STATE,
)

from .actions import (
    # Action types
    ActionType,
    Action,
    # Payloads
    SetThemePayload,
    SetPagePayload,
    SelectDevicePayload,
    LoadDevicesPayload,
    SystemStatusPayload,
    SyncCompletedPayload,
    # Action creators
    set_theme,
    toggle_theme,
    set_page,
    toggle_sidebar,
    set_sidebar,
    toggle_right_panel,
    set_right_panel,
    set_loading,
    set_error,
    clear_error,
    select_device,
    select_device_only,
    deselect_device,
    set_selected_device_gantt,
    load_devices,
    update_devices,
    update_device,
    load_gantt,
    set_page_devices,
    set_data_range,
    update_system_status,
    sync_started,
    sync_completed,
    sync_failed,
    batch_actions,
)

from .reducers import (
    root_reducer,
    root_reducer_dict,
    INITIAL_STATE_DICT,
    combine_reducers,
    # Sub-reducers
    theme_reducer,
    navigation_reducer,
    ui_reducer,
    selection_reducer,
    devices_reducer,
    gantt_reducer,
    settings_reducer,
    system_reducer,
)

from .selectors import (
    # Memoization
    MemoizedSelector,
    create_selector,
    create_derived_selector,
    # Basic selectors
    select_theme,
    select_theme_mode,
    select_current_page,
    select_current_page_id,
    select_sidebar_expanded,
    select_right_panel_expanded,
    select_is_loading,
    select_error,
    select_ui_state,
    select_data_range_days,
    # Device selectors
    select_devices,
    select_devices_list,
    select_device_by_id,
    select_device_count,
    # Selection selectors
    select_selected_device_id,
    select_selected_device,
    select_has_selection,
    select_selected_device_gantt,
    # Computed selectors
    select_factory_summary,
    select_factory_summary_typed,
    select_system_status,
    # Memoized instances
    memoized_select_theme,
    memoized_select_devices,
    memoized_select_factory_summary,
    # Derived selectors
    select_running_devices,
    select_alarm_devices,
    select_devices_by_status,
)

from .store import (
    Store,
    EnhancedStore,
    StoreConfig,
    # Protocols
    Middleware,
    IStatePersistence,
    # Middleware
    logging_middleware,
    performance_middleware,
    dev_tools_middleware,
    create_persistence_middleware,
    # Persistence
    LocalStoragePersistence,
    # Time travel
    StateSnapshot,
    StateHistory,
)


__all__ = [
    # Types
    "ThemeMode",
    "PageId",
    "ConnectionStatus",
    "SystemStatus",
    "DeviceSnapshot",
    "GanttSegment",
    "FactorySummary",
    "UIState",
    "SelectionState",
    "AppState",
    "create_initial_state",
    "INITIAL_STATE",
    # Actions
    "ActionType",
    "Action",
    "set_theme",
    "toggle_theme",
    "set_page",
    "toggle_sidebar",
    "toggle_right_panel",
    "set_loading",
    "set_error",
    "clear_error",
    "select_device",
    "select_device_only",
    "deselect_device",
    "load_devices",
    "update_devices",
    "set_data_range",
    "update_system_status",
    "sync_completed",
    "batch_actions",
    # Reducers
    "root_reducer",
    "root_reducer_dict",
    "INITIAL_STATE_DICT",
    "combine_reducers",
    # Selectors
    "MemoizedSelector",
    "create_selector",
    "create_derived_selector",
    "select_theme",
    "select_current_page",
    "select_devices",
    "select_selected_device_id",
    "select_factory_summary",
    "select_system_status",
    # Store
    "Store",
    "EnhancedStore",
    "StoreConfig",
    "Middleware",
    "logging_middleware",
    "LocalStoragePersistence",
]
