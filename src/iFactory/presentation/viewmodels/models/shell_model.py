"""
Shell Data Models.

Pure data classes for shell/navigation state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class SystemStatusModel:
    """System connection status."""

    mssql_connected: bool = False
    sqlite_connected: bool = False
    message: str = ""
    last_sync_time: Optional[datetime] = None  # ✅ ADD: Track sync timestamp

    @property
    def is_online(self) -> bool:
        return self.mssql_connected

    @property
    def status_text(self) -> str:
        if self.is_online:
            return "ONLINE"
        if self.sqlite_connected:
            return "OFFLINE MODE"
        return "DISCONNECTED"

    @property
    def status_color(self) -> str:
        if self.is_online:
            return "#10B981"  # Green
        if self.sqlite_connected:
            return "#F59E0B"  # Amber
        return "#EF4444"  # Red

    # ✅ ADD: Format sync time for display
    @property
    def formatted_sync_time(self) -> str:
        """Human-readable sync time."""
        if not self.last_sync_time:
            return "Never"

        delta = datetime.now() - self.last_sync_time
        seconds = int(delta.total_seconds())

        if seconds < 10:
            return "Just now"
        elif seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        else:
            return f"{seconds // 3600}h ago"

    # ✅ ADD: Check if data is stale
    @property
    def is_stale(self) -> bool:
        """Check if sync data is stale (>30 seconds)."""
        if not self.last_sync_time:
            return True
        delta = (datetime.now() - self.last_sync_time).total_seconds()
        return delta > 30


@dataclass(frozen=True, slots=True)
class ShellStateModel:
    """Complete shell state."""

    theme: str = "light"
    current_page: str = "electrode_page"
    sidebar_expanded: bool = False
    right_panel_expanded: bool = False
    selected_device_id: Optional[str] = None
    is_loading: bool = False
    error: Optional[str] = None
    system_status: Optional[SystemStatusModel] = None

    def __post_init__(self):
        if self.system_status is None:
            object.__setattr__(self, "system_status", SystemStatusModel())

    @property
    def is_dark(self) -> bool:
        return self.theme == "dark"

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def has_selection(self) -> bool:
        return self.selected_device_id is not None


@dataclass(frozen=True, slots=True)
class NavigationItem:
    """Navigation menu item."""

    id: str
    label: str
    icon: str
    icon_white: str
    page: str
    is_active: bool = False


__all__ = [
    "SystemStatusModel",
    "ShellStateModel",
    "NavigationItem",
]
