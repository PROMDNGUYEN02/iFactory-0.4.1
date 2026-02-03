# File: presentation/viewmodels/shell_viewmodel.py
"""
Shell ViewModel.

Manages shell/navigation state including:
- Theme (light/dark) via ThemeService
- Current page
- Sidebar expansion
- Right panel expansion
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import Signal

from .base import BaseViewModel, UiState
from .models.shell_model import SystemStatusModel

if TYPE_CHECKING:
    from ..services.page_device_manager import PageDeviceManager
    from ..services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class ShellViewModel(BaseViewModel):
    """
    ViewModel for Shell (main application frame).

    Manages:
    - Theme switching (via injected ThemeService)
    - Page navigation
    - Panel states
    - System status
    """

    themeChanged = Signal(str)
    pageChanged = Signal(str)
    sidebarChanged = Signal(bool)
    rightPanelChanged = Signal(bool)
    systemStatusChanged = Signal(object)

    def __init__(
        self,
        theme_service: Optional["ThemeService"] = None,
        config_path: Optional[Path] = None,
        page_manager: Optional["PageDeviceManager"] = None,
        parent=None,
    ):
        super().__init__(parent)

        # Inject theme service or fall back to global
        if theme_service is None:
            from ..services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._config_path = config_path
        self._page_manager = page_manager

        # State
        self._current_page: str = "electrode_page"
        self._sidebar_expanded: bool = False
        self._right_panel_expanded: bool = False
        self._system_status = SystemStatusModel()

        # Cache
        self._layout_cache: Dict[str, Any] = {}

        # Forward theme service signals
        self._theme_service.themeChanged.connect(self._on_theme_service_changed)

    def _on_theme_service_changed(self, theme: str) -> None:
        """Forward theme changes from service."""
        self.themeChanged.emit(theme)

    def initialize(self) -> None:
        """Initialize shell state."""
        self._set_state(UiState.success())
        logger.info("[ShellViewModel] Initialized")

    # =========================================================================
    # Configuration
    # =========================================================================

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        """Set page manager for coordinated navigation."""
        self._page_manager = manager

    # =========================================================================
    # Theme Properties (Delegated to ThemeService)
    # =========================================================================

    @property
    def theme(self) -> str:
        """Get current theme name."""
        return self._theme_service.current_theme

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark."""
        return self._theme_service.is_dark

    @property
    def theme_service(self) -> "ThemeService":
        """Expose theme service for views that need direct access."""
        return self._theme_service

    # =========================================================================
    # Other Properties
    # =========================================================================

    @property
    def current_page(self) -> str:
        return self._current_page

    @property
    def sidebar_expanded(self) -> bool:
        return self._sidebar_expanded

    @property
    def right_panel_expanded(self) -> bool:
        return self._right_panel_expanded

    @property
    def system_status(self) -> SystemStatusModel:
        return self._system_status

    # =========================================================================
    # Theme Actions
    # =========================================================================

    def toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        self._theme_service.toggle_theme()
        logger.info(f"[ShellViewModel] Theme: {self.theme}")

    def set_theme(self, theme: str) -> None:
        """Set specific theme."""
        self._theme_service.set_theme(theme)

    # =========================================================================
    # Navigation Actions
    # =========================================================================

    def navigate_to(self, page: str) -> None:
        """Navigate to a page."""
        normalized = page.replace("daboard", "electrode")
        if not normalized.endswith("_page"):
            normalized = f"{normalized}_page"

        if normalized == self._current_page:
            return

        logger.info(f"[ShellViewModel] Navigating to {normalized}")

        if self._page_manager:
            self._page_manager.set_current_page(normalized)

        self._current_page = normalized
        self.pageChanged.emit(normalized)

    # =========================================================================
    # Panel Actions
    # =========================================================================

    def toggle_sidebar(self) -> None:
        """Toggle sidebar expansion."""
        self._sidebar_expanded = not self._sidebar_expanded
        self.sidebarChanged.emit(self._sidebar_expanded)
        logger.debug(f"[ShellViewModel] Sidebar expanded: {self._sidebar_expanded}")

    def set_sidebar_expanded(self, expanded: bool) -> None:
        """Set sidebar expansion state."""
        if expanded != self._sidebar_expanded:
            self._sidebar_expanded = expanded
            self.sidebarChanged.emit(expanded)

    def toggle_right_panel(self) -> None:
        """Toggle right details panel."""
        self._right_panel_expanded = not self._right_panel_expanded
        self.rightPanelChanged.emit(self._right_panel_expanded)
        logger.debug(f"[ShellViewModel] Right panel expanded: {self._right_panel_expanded}")

    def open_right_panel(self) -> None:
        """Open right panel."""
        if not self._right_panel_expanded:
            self._right_panel_expanded = True
            self.rightPanelChanged.emit(True)
            logger.debug("[ShellViewModel] Right panel opened")

    def close_right_panel(self) -> None:
        """Close right panel."""
        if self._right_panel_expanded:
            self._right_panel_expanded = False
            self.rightPanelChanged.emit(False)
            logger.debug("[ShellViewModel] Right panel closed")

    def set_right_panel_expanded(self, expanded: bool) -> None:
        """Set right panel expansion state."""
        if expanded != self._right_panel_expanded:
            self._right_panel_expanded = expanded
            self.rightPanelChanged.emit(expanded)

    # =========================================================================
    # System Status
    # =========================================================================

    def update_system_status(
        self,
        mssql_connected: Optional[bool] = None,
        sqlite_connected: Optional[bool] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update system connection status."""
        self._system_status = SystemStatusModel(
            mssql_connected=(mssql_connected if mssql_connected is not None else self._system_status.mssql_connected),
            sqlite_connected=(sqlite_connected if sqlite_connected is not None else self._system_status.sqlite_connected),
            message=message if message is not None else self._system_status.message,
        )
        self.systemStatusChanged.emit(self._system_status)

    # =========================================================================
    # Layout Configuration
    # =========================================================================

    def get_layout_config(self, area_key: str) -> Dict[str, Any]:
        """Get layout configuration for an area."""
        if area_key in self._layout_cache:
            return self._layout_cache[area_key]

        if not self._config_path or not self._config_path.exists():
            return {}

        try:
            text = self._config_path.read_text(encoding="utf-8")
            data = json.loads(text)

            config = data.get(area_key, {})
            if not config:
                for key in data:
                    if area_key in key or key in area_key:
                        config = data[key]
                        break

            self._layout_cache[area_key] = config
            return config

        except Exception as e:
            logger.error(f"[ShellViewModel] Failed to load layout config: {e}")
            return {}

    # =========================================================================
    # State Serialization
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary."""
        return {
            "theme": self.theme,
            "current_page": self._current_page,
            "sidebar_expanded": self._sidebar_expanded,
            "right_panel_expanded": self._right_panel_expanded,
            "system_status": {
                "mssql": self._system_status.mssql_connected,
                "sqlite": self._system_status.sqlite_connected,
                "message": self._system_status.message,
            },
        }

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
        self._layout_cache.clear()
        super().dispose()


__all__ = ["ShellViewModel"]
