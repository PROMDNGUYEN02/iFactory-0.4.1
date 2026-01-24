"""
Centralized Icon Management System.

Provides single source of truth for all icons used in the application.
Supports theme-aware icon paths and lazy loading.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QSize, QObject, Signal
from PySide6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)


class IconSize(Enum):
    """Standard icon sizes."""

    XS = 16
    SM = 20
    MD = 24
    LG = 32
    XL = 48
    XXL = 64


class IconCategory(Enum):
    """Icon categories."""

    UI = "ui"
    DEVICE = "device"
    STATUS = "status"
    NAVIGATION = "navigation"
    ACTION = "action"
    EDITOR = "editor"


@dataclass(frozen=True, slots=True)
class IconDefinition:
    """Icon definition with theme variants."""

    name: str
    category: IconCategory
    path_light: str
    path_dark: str | None = None
    size: IconSize = IconSize.MD

    def get_path(self, theme: str = "light") -> str:
        """Get icon path for theme."""
        if theme == "dark" and self.path_dark:
            return self.path_dark
        return self.path_light


class IconManager(QObject):
    """
    Centralized Icon Management System.

    Features:
        - Single source of truth for all icons
        - Theme-aware icon paths
        - Lazy loading with caching
        - Size scaling support
        - Error handling for missing icons

    Usage:
        ```python
        icon_manager = IconManager()

        # Get icon
        icon = icon_manager.get_icon("dashboard")

        # Get themed icon
        icon = icon_manager.get_icon("dashboard", theme="dark")

        # Get specific size
        icon = icon_manager.get_icon("dashboard", size=IconSize.LG)

        # Get icon name by category
        icons = icon_manager.get_icons_by_category(IconCategory.DEVICE)
        ```
    """

    icon_loaded = Signal(str)
    icon_error = Signal(str, str)

    ICON_DEFINITIONS: Dict[str, IconDefinition] = {
        "dashboard": IconDefinition(
            "dashboard",
            IconCategory.NAVIGATION,
            ":/icon/dashboard.svg",
            ":/icon/dashboard-white.svg",
            IconSize.MD
        ),
        "orders": IconDefinition(
            "orders",
            IconCategory.NAVIGATION,
            ":/icon/orders.svg",
            ":/icon/orders-white.svg",
            IconSize.MD
        ),
        "products": IconDefinition(
            "products",
            IconCategory.NAVIGATION,
            ":/icon/products.svg",
            ":/icon/products-white.svg",
            IconSize.MD
        ),
        "customers": IconDefinition(
            "customers",
            IconCategory.NAVIGATION,
            ":/icon/customers.svg",
            ":/icon/customers-white.svg",
            IconSize.MD
        ),
        "reports": IconDefinition(
            "reports",
            IconCategory.NAVIGATION,
            ":/icon/reports.svg",
            ":/icon/reports-white.svg",
            IconSize.MD
        ),
        "settings": IconDefinition(
            "settings",
            IconCategory.UI,
            ":/icon/settings.svg",
            ":/icon/settings-white.svg",
            IconSize.MD
        ),
        "menu-open": IconDefinition(
            "menu-open",
            IconCategory.UI,
            ":/icon/arrow_menu_open.svg",
            ":/icon/arrow_menu_open-white.svg",
            IconSize.MD
        ),
        "menu-close": IconDefinition(
            "menu-close",
            IconCategory.UI,
            ":/icon/arrow_menu_close.svg",
            ":/icon/arrow_menu_close-white.svg",
            IconSize.MD
        ),
        "expand": IconDefinition(
            "expand",
            IconCategory.UI,
            ":/icon/expand.svg",
            ":/icon/expand-white.svg",
            IconSize.MD
        ),
        "close": IconDefinition(
            "close",
            IconCategory.UI,
            ":/icon/close.svg",
            ":/icon/close-white.svg",
            IconSize.SM
        ),
        "logo": IconDefinition(
            "logo",
            IconCategory.UI,
            ":/icon/logo.png",
            ":/icon/logo.png",
            IconSize.XL
        ),
        "status-running": IconDefinition(
            "status-running",
            IconCategory.STATUS,
            ":/icon/status-running.svg",
            ":/icon/status-running-dark.svg",
            IconSize.SM
        ),
        "status-shutdown": IconDefinition(
            "status-shutdown",
            IconCategory.STATUS,
            ":/icon/status-shutdown.svg",
            ":/icon/status-shutdown-dark.svg",
            IconSize.SM
        ),
        "status-stop": IconDefinition(
            "status-stop",
            IconCategory.STATUS,
            ":/icon/status-stop.svg",
            ":/icon/status-stop-dark.svg",
            IconSize.SM
        ),
        "status-maintenance": IconDefinition(
            "status-maintenance",
            IconCategory.STATUS,
            ":/icon/status-maintenance.svg",
            ":/icon/status-maintenance-dark.svg",
            IconSize.SM
        ),
        "status-alarm": IconDefinition(
            "status-alarm",
            IconCategory.STATUS,
            ":/icon/status-alarm.svg",
            ":/icon/status-alarm-dark.svg",
            IconSize.SM
        ),
        "status-unknown": IconDefinition(
            "status-unknown",
            IconCategory.STATUS,
            ":/icon/status-unknown.svg",
            ":/icon/status-unknown-dark.svg",
            IconSize.SM
        ),
        "refresh": IconDefinition(
            "refresh",
            IconCategory.ACTION,
            ":/icon/refresh.svg",
            ":/icon/refresh-white.svg",
            IconSize.SM
        ),
        "edit": IconDefinition(
            "edit",
            IconCategory.ACTION,
            ":/icon/edit.svg",
            ":/icon/edit-white.svg",
            IconSize.SM
        ),
        "delete": IconDefinition(
            "delete",
            IconCategory.ACTION,
            ":/icon/delete.svg",
            ":/icon/delete-white.svg",
            IconSize.SM
        ),
        "add": IconDefinition(
            "add",
            IconCategory.ACTION,
            ":/icon/add.svg",
            ":/icon/add-white.svg",
            IconSize.SM
        ),
        "search": IconDefinition(
            "search",
            IconCategory.UI,
            ":/icon/search.svg",
            ":/icon/search-white.svg",
            IconSize.SM
        ),
        "filter": IconDefinition(
            "filter",
            IconCategory.UI,
            ":/icon/filter.svg",
            ":/icon/filter-white.svg",
            IconSize.SM
        ),
        "download": IconDefinition(
            "download",
            IconCategory.ACTION,
            ":/icon/download.svg",
            ":/icon/download-white.svg",
            IconSize.SM
        ),
        "upload": IconDefinition(
            "upload",
            IconCategory.ACTION,
            ":/icon/upload.svg",
            ":/icon/upload-white.svg",
            IconSize.SM
        ),
        "save": IconDefinition(
            "save",
            IconCategory.ACTION,
            ":/icon/save.svg",
            ":/icon/save-white.svg",
            IconSize.SM
        ),
        "fullscreen": IconDefinition(
            "fullscreen",
            IconCategory.UI,
            ":/icon/fullscreen.svg",
            ":/icon/fullscreen-white.svg",
            IconSize.SM
        ),
        "exit-fullscreen": IconDefinition(
            "exit-fullscreen",
            IconCategory.UI,
            ":/icon/exit-fullscreen.svg",
            ":/icon/exit-fullscreen-white.svg",
            IconSize.SM
        ),
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._theme: str = "light"
        self._cache: Dict[str, QIcon] = {}
        self._pixmap_cache: Dict[Tuple[str, QSize], QPixmap] = {}
        logger.debug("[IconManager] Initialized")

    def set_theme(self, theme: str) -> None:
        """
        Set current theme.

        Args:
            theme: 'light' or 'dark'
        """
        self._theme = theme
        self.clear_cache()
        logger.debug(f"[IconManager] Theme: {theme}")

    @property
    def theme(self) -> str:
        """Get current theme."""
        return self._theme

    def get_icon(
        self,
        name: str,
        size: IconSize | QSize | None = None,
        theme: str | None = None
    ) -> QIcon:
        """
        Get icon by name.

        Args:
            name: Icon name (from ICON_DEFINITIONS)
            size: Icon size (default: from definition)
            theme: Theme mode (default: current theme)

        Returns:
            QIcon instance
        """
        definition = self.ICON_DEFINITIONS.get(name)
        if not definition:
            logger.warning(f"[IconManager] Icon not found: {name}")
            return QIcon()

        theme = theme or self._theme
        path = definition.get_path(theme)

        cache_key = f"{name}_{theme}"
        if cache_key not in self._cache:
            icon = QIcon(path)
            if icon.isNull():
                logger.error(f"[IconManager] Failed to load icon: {path}")
                self.icon_error.emit(name, "Failed to load icon")
                return QIcon()
            self._cache[cache_key] = icon
            self.icon_loaded.emit(name)

        return self._cache[cache_key]

    def get_pixmap(
        self,
        name: str,
        size: IconSize | QSize | None = None,
        theme: str | None = None
    ) -> QPixmap:
        """
        Get pixmap by name and size.

        Args:
            name: Icon name
            size: Size (default: from definition)
            theme: Theme mode

        Returns:
            QPixmap instance
        """
        definition = self.ICON_DEFINITIONS.get(name)
        if not definition:
            return QPixmap()

        if size is None:
            size = definition.size
        if isinstance(size, IconSize):
            size = QSize(size.value, size.value)

        theme = theme or self._theme
        cache_key = (f"{name}_{theme}", size)

        if cache_key not in self._pixmap_cache:
            icon = self.get_icon(name, size=size, theme=theme)
            pixmap = icon.pixmap(size)
            if pixmap.isNull():
                return QPixmap()
            self._pixmap_cache[cache_key] = pixmap

        return self._pixmap_cache[cache_key]

    def get_icon_path(self, name: str, theme: str | None = None) -> str:
        """
        Get icon file path.

        Args:
            name: Icon name
            theme: Theme mode

        Returns:
            File path string
        """
        definition = self.ICON_DEFINITIONS.get(name)
        if not definition:
            return ""
        return definition.get_path(theme or self._theme)

    def get_icons_by_category(self, category: IconCategory) -> Dict[str, IconDefinition]:
        """
        Get all icons in a category.

        Args:
            category: Icon category

        Returns:
            Dictionary of icon name → definition
        """
        return {
            name: definition
            for name, definition in self.ICON_DEFINITIONS.items()
            if definition.category == category
        }

    def get_all_icon_names(self) -> list[str]:
        """Get list of all available icon names."""
        return list(self.ICON_DEFINITIONS.keys())

    def add_icon_definition(self, definition: IconDefinition) -> None:
        """
        Add or update icon definition.

        Args:
            definition: Icon definition
        """
        self.ICON_DEFINITIONS[definition.name] = definition
        self.clear_cache()

    def clear_cache(self) -> None:
        """Clear all cached icons and pixmaps."""
        self._cache.clear()
        self._pixmap_cache.clear()
        logger.debug("[IconManager] Cache cleared")

    def preload_icons(self, names: list[str] | None = None) -> None:
        """
        Preload icons into cache.

        Args:
            names: List of icon names (default: all icons)
        """
        icon_names = names or self.get_all_icon_names()
        for name in icon_names:
            self.get_icon(name)
        logger.debug(f"[IconManager] Preloaded {len(icon_names)} icons")


__all__ = [
    "IconManager",
    "IconSize",
    "IconCategory",
    "IconDefinition",
]
