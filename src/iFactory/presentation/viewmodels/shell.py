# File: presentation/viewmodels/shell.py
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class SystemStatusViewModel:
    mssql_connected: bool
    sqlite_connected: bool
    message: str
    is_online: bool

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
            return "#10B981"
        if self.sqlite_connected:
            return "#F59E0B"
        return "#EF4444"


@dataclass(frozen=True, slots=True)
class ShellViewModel:
    theme: str
    current_page: str
    sidebar_expanded: bool
    right_panel_expanded: bool
    selected_device_id: Optional[str]
    is_loading: bool
    error: Optional[str]
    system_status: SystemStatusViewModel

    @property
    def is_dark(self) -> bool:
        return self.theme == "dark"

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def has_selection(self) -> bool:
        return self.selected_device_id is not None
