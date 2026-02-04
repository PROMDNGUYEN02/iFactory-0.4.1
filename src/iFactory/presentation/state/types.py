# src/iFactory/presentation/state/types.py
"""
Strongly typed state definitions.

Uses frozen dataclasses for immutability and type safety.
All state mutations must go through actions/reducers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple, TypeVar, Generic

T = TypeVar("T")


# ============================================================================
# Enums
# ============================================================================


class ThemeMode(str, Enum):
    """Application theme modes."""

    LIGHT = "light"
    DARK = "dark"

    @classmethod
    def from_string(cls, value: str) -> "ThemeMode":
        try:
            return cls(value.lower())
        except ValueError:
            return cls.LIGHT


class PageId(str, Enum):
    """Available page identifiers."""

    ELECTRODE = "electrode_page"
    ASSEMBLY = "assembly_page"
    REPORTS = "reports_page"
    SETTINGS = "settings_page"

    @classmethod
    def from_string(cls, value: str) -> "PageId":
        # Handle legacy names
        normalized = value.replace("daboard", "electrode")
        try:
            return cls(normalized)
        except ValueError:
            return cls.ELECTRODE


class ConnectionStatus(Enum):
    """Database connection status."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


# ============================================================================
# Immutable Value Objects
# ============================================================================


@dataclass(frozen=True, slots=True)
class SystemStatus:
    """System connection status - immutable."""

    mssql_connected: bool = False
    sqlite_connected: bool = False
    message: str = ""
    last_check: Optional[datetime] = None

    def with_mssql(self, connected: bool, message: str = "") -> "SystemStatus":
        return SystemStatus(
            mssql_connected=connected,
            sqlite_connected=self.sqlite_connected,
            message=message or self.message,
            last_check=datetime.now(),
        )

    def with_sqlite(self, connected: bool) -> "SystemStatus":
        return SystemStatus(
            mssql_connected=self.mssql_connected,
            sqlite_connected=connected,
            message=self.message,
            last_check=datetime.now(),
        )


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    """
    Immutable snapshot of device state.

    Used in the store instead of mutable Device entities.
    """

    device_id: str
    equipment_code: str
    status_code: int = 0
    status_name: str = ""
    input_count: int = 0
    output_count: int = 0
    ng_count: int = 0
    current_model: str = ""
    current_lot: str = ""
    last_update: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self.status_code == 1

    @property
    def is_stopped(self) -> bool:
        return self.status_code == 3

    @property
    def is_alarm(self) -> bool:
        return self.status_code == 5

    @property
    def yield_rate(self) -> float:
        if self.input_count == 0:
            return 0.0
        return (self.output_count / self.input_count) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for backward compatibility."""
        return {
            "device_id": self.device_id,
            "equipment_code": self.equipment_code,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "ng_count": self.ng_count,
            "current_model": self.current_model,
            "current_lot": self.current_lot,
            "last_update": self.last_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceSnapshot":
        """Create from dict."""
        return cls(
            device_id=data.get("device_id", ""),
            equipment_code=data.get("equipment_code", ""),
            status_code=data.get("status_code", 0),
            status_name=data.get("status_name", ""),
            input_count=data.get("input_count", 0),
            output_count=data.get("output_count", 0),
            ng_count=data.get("ng_count", 0),
            current_model=data.get("current_model", ""),
            current_lot=data.get("current_lot", ""),
            last_update=data.get("last_update"),
        )


@dataclass(frozen=True, slots=True)
class GanttSegment:
    """Immutable Gantt chart segment."""

    start_time: datetime
    end_time: datetime
    status_code: int
    status_name: str = ""

    @property
    def duration_minutes(self) -> float:
        return (self.end_time - self.start_time).total_seconds() / 60


@dataclass(frozen=True, slots=True)
class FactorySummary:
    """Computed factory statistics - immutable."""

    total_devices: int = 0
    running_count: int = 0
    stopped_count: int = 0
    alarm_count: int = 0
    idle_count: int = 0
    total_input: int = 0
    total_output: int = 0
    total_ng: int = 0

    @property
    def yield_rate(self) -> float:
        if self.total_input == 0:
            return 0.0
        return (self.total_output / self.total_input) * 100

    @property
    def ng_rate(self) -> float:
        if self.total_input == 0:
            return 0.0
        return (self.total_ng / self.total_input) * 100


@dataclass(frozen=True, slots=True)
class UIState:
    """UI-related state - immutable."""

    sidebar_expanded: bool = False
    right_panel_expanded: bool = False
    is_loading: bool = False
    error_message: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SelectionState:
    """Selection state - immutable."""

    selected_device_id: Optional[str] = None
    selected_gantt: Optional[Any] = None  # GanttChartViewModel reference

    @property
    def has_selection(self) -> bool:
        return self.selected_device_id is not None


# ============================================================================
# Root Application State
# ============================================================================


@dataclass(frozen=True)
class AppState:
    """
    Root application state - completely immutable.

    All state is stored as frozen dataclasses or immutable collections.
    State updates return new instances.
    """

    # Theme & Navigation
    theme: ThemeMode = ThemeMode.LIGHT
    current_page: PageId = PageId.ELECTRODE

    # UI State
    ui: UIState = field(default_factory=UIState)

    # Selection
    selection: SelectionState = field(default_factory=SelectionState)

    # Data
    devices: Tuple[DeviceSnapshot, ...] = ()
    gantt_data: Tuple[Tuple[str, Tuple[GanttSegment, ...]], ...] = ()
    page_devices: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()

    # Settings
    data_range_days: int = 1

    # System Status
    system_status: SystemStatus = field(default_factory=SystemStatus)
    last_sync: Optional[datetime] = None

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_device(self, device_id: str) -> Optional[DeviceSnapshot]:
        """Get device by ID."""
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None

    def get_devices_dict(self) -> Dict[str, DeviceSnapshot]:
        """Get devices as dict for backward compatibility."""
        return {d.device_id: d for d in self.devices}

    def get_gantt_for_device(self, device_id: str) -> Tuple[GanttSegment, ...]:
        """Get Gantt segments for a device."""
        for dev_id, segments in self.gantt_data:
            if dev_id == device_id:
                return segments
        return ()

    def get_page_device_ids(self, page: str) -> Tuple[str, ...]:
        """Get device IDs for a page."""
        for page_id, device_ids in self.page_devices:
            if page_id == page:
                return device_ids
        return ()

    @property
    def selected_device(self) -> Optional[DeviceSnapshot]:
        """Get currently selected device."""
        if not self.selection.selected_device_id:
            return None
        return self.get_device(self.selection.selected_device_id)

    def compute_factory_summary(self) -> FactorySummary:
        """Compute factory summary from current devices."""
        if not self.devices:
            return FactorySummary()

        running = stopped = alarm = idle = 0
        total_input = total_output = total_ng = 0

        for device in self.devices:
            total_input += device.input_count
            total_output += device.output_count
            total_ng += device.ng_count

            if device.status_code == 1:
                running += 1
            elif device.status_code == 3:
                stopped += 1
            elif device.status_code == 5:
                alarm += 1
            else:
                idle += 1

        return FactorySummary(
            total_devices=len(self.devices),
            running_count=running,
            stopped_count=stopped,
            alarm_count=alarm,
            idle_count=idle,
            total_input=total_input,
            total_output=total_output,
            total_ng=total_ng,
        )

    # ========================================================================
    # State Update Methods (return new immutable state)
    # ========================================================================

    def with_theme(self, theme: ThemeMode) -> "AppState":
        """Return new state with updated theme."""
        return AppState(
            theme=theme,
            current_page=self.current_page,
            ui=self.ui,
            selection=self.selection,
            devices=self.devices,
            gantt_data=self.gantt_data,
            page_devices=self.page_devices,
            data_range_days=self.data_range_days,
            system_status=self.system_status,
            last_sync=self.last_sync,
        )

    def with_page(self, page: PageId) -> "AppState":
        """Return new state with updated page."""
        return AppState(
            theme=self.theme,
            current_page=page,
            ui=self.ui,
            selection=self.selection,
            devices=self.devices,
            gantt_data=self.gantt_data,
            page_devices=self.page_devices,
            data_range_days=self.data_range_days,
            system_status=self.system_status,
            last_sync=self.last_sync,
        )

    def with_ui(self, ui: UIState) -> "AppState":
        """Return new state with updated UI state."""
        return AppState(
            theme=self.theme,
            current_page=self.current_page,
            ui=ui,
            selection=self.selection,
            devices=self.devices,
            gantt_data=self.gantt_data,
            page_devices=self.page_devices,
            data_range_days=self.data_range_days,
            system_status=self.system_status,
            last_sync=self.last_sync,
        )

    def with_selection(self, selection: SelectionState) -> "AppState":
        """Return new state with updated selection."""
        return AppState(
            theme=self.theme,
            current_page=self.current_page,
            ui=self.ui,
            selection=selection,
            devices=self.devices,
            gantt_data=self.gantt_data,
            page_devices=self.page_devices,
            data_range_days=self.data_range_days,
            system_status=self.system_status,
            last_sync=self.last_sync,
        )

    def with_devices(self, devices: Tuple[DeviceSnapshot, ...]) -> "AppState":
        """Return new state with updated devices."""
        return AppState(
            theme=self.theme,
            current_page=self.current_page,
            ui=self.ui,
            selection=self.selection,
            devices=devices,
            gantt_data=self.gantt_data,
            page_devices=self.page_devices,
            data_range_days=self.data_range_days,
            system_status=self.system_status,
            last_sync=self.last_sync,
        )

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for backward compatibility.

        NOTE: This is for compatibility with existing code.
        New code should use typed state directly.
        """
        return {
            "theme": self.theme.value,
            "current_page": self.current_page.value,
            "sidebar_expanded": self.ui.sidebar_expanded,
            "right_panel_expanded": self.ui.right_panel_expanded,
            "is_loading": self.ui.is_loading,
            "error": self.ui.error_message,
            "selected_device_id": self.selection.selected_device_id,
            "selected_device_gantt": self.selection.selected_gantt,
            "devices": {d.device_id: d.to_dict() for d in self.devices},
            "gantt_data": {
                dev_id: [
                    {
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "status_code": seg.status_code,
                        "status_name": seg.status_name,
                    }
                    for seg in segments
                ]
                for dev_id, segments in self.gantt_data
            },
            "page_devices": {page: list(devs) for page, devs in self.page_devices},
            "data_range_days": self.data_range_days,
            "system_status": {
                "mssql": self.system_status.mssql_connected,
                "sqlite": self.system_status.sqlite_connected,
                "message": self.system_status.message,
            },
            "last_sync": self.last_sync,
        }


# ============================================================================
# Initial State Factory
# ============================================================================


def create_initial_state() -> AppState:
    """Create initial application state."""
    return AppState()


# For backward compatibility
INITIAL_STATE = create_initial_state()


__all__ = [
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
]
