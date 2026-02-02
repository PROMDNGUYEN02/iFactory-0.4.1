# File: presentation/services/icon_service.py
"""
Icon Service - Unified icon management API.

This is the PRIMARY interface for all icon operations.
Combines resolution, caching, and theme awareness.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QIcon, QPixmap

from ..resources.icons.registry import Icons, DeviceIcons, IconCategory
from ..resources.icons.resolver import IconResolver
from ..resources.icons.provider import IconProvider, get_icon_provider

if TYPE_CHECKING:
    from .theme_service import ThemeService

logger = logging.getLogger(__name__)


class IconService(QObject):
    """
    Unified icon management service.

    Usage:
        # Get service
        icon_service = get_icon_service()

        # Using enums (preferred)
        icon = icon_service.get_icon(Icons.DASHBOARD)
        pixmap = icon_service.get_pixmap(Icons.SETTINGS, QSize(32, 32))

        # Using device codes
        device_icon = icon_service.get_device_icon("ACL")

        # Legacy string paths (backward compatible)
        icon = icon_service.get_icon(":/icon/dashboard.svg")
    """

    # Emitted when icons should be refreshed (theme change)
    icons_invalidated = Signal()

    def __init__(self, theme_service: "ThemeService"):
        super().__init__()
        self._theme_service = theme_service
        self._provider = get_icon_provider(theme_service)
        self._resolver = IconResolver(theme_service)

        # Connect to theme changes
        theme_service.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self.icons_invalidated.emit()

    # =========================================================================
    # Primary API - Enum-based (Recommended)
    # =========================================================================

    def get_icon(self, icon: Union[Icons, DeviceIcons, str]) -> QIcon:
        """
        Get QIcon for the given icon.

        Args:
            icon: Icon enum or legacy string path

        Returns:
            Theme-appropriate QIcon (cached)
        """
        return self._provider.get_icon(icon)

    def get_pixmap(self, icon: Union[Icons, DeviceIcons, str], size: Optional[QSize] = None) -> QPixmap:
        """
        Get QPixmap for the given icon.

        Args:
            icon: Icon enum or legacy string path
            size: Desired size

        Returns:
            Theme-appropriate QPixmap (cached)
        """
        return self._provider.get_pixmap(icon, size)

    def get_path(self, icon: Union[Icons, DeviceIcons, str]) -> str:
        """
        Get resolved resource path for the given icon.

        Args:
            icon: Icon enum or legacy string path

        Returns:
            Theme-appropriate resource path string
        """
        return self._resolver.resolve(icon)

    # =========================================================================
    # Device-specific API
    # =========================================================================

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get QIcon for a device by equipment code."""
        return self._provider.get_device_icon(equipment_code)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get QPixmap for a device by equipment code."""
        return self._provider.get_device_pixmap(equipment_code, size)

    def get_device_path(self, equipment_code: str) -> str:
        """Get resolved path for a device icon."""
        return self._resolver.resolve_device(equipment_code)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def preload_navigation_icons(self) -> None:
        """Preload all navigation icons for fast startup."""
        nav_icons = Icons.by_category(IconCategory.NAVIGATION)
        self._provider.preload(nav_icons)

    def preload_device_icons(self, codes: list[str]) -> None:
        """Preload device icons for specific equipment codes."""
        device_icons = [DeviceIcons.from_code(code) for code in codes if DeviceIcons.from_code(code)]
        self._provider.preload(device_icons)

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    @property
    def cache_stats(self) -> dict:
        """Get icon cache statistics."""
        return self._provider.cache_stats


# Module singleton
_service_instance: Optional[IconService] = None


def get_icon_service(theme_service: Optional["ThemeService"] = None) -> IconService:
    """
    Get the global IconService instance.

    Args:
        theme_service: Required on first call

    Returns:
        Global IconService singleton
    """
    global _service_instance

    if _service_instance is None:
        if theme_service is None:
            from .theme_service import get_theme_service

            theme_service = get_theme_service()
        _service_instance = IconService(theme_service)

    return _service_instance


__all__ = [
    "IconService",
    "get_icon_service",
    "Icons",
    "DeviceIcons",
]
