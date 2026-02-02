# File: presentation/services/icon_service.py
"""
Icon Service - Unified icon management API.

This is the PRIMARY interface for all icon operations.
Combines resolution, caching, and theme awareness.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor

from ..resources.icons.registry import Icons, DeviceIcons, IconCategory
from ..resources.icons.provider import IconProvider, get_icon_provider

if TYPE_CHECKING:
    from .theme_service import ThemeService

logger = logging.getLogger(__name__)


class IconSize:
    """Standard icon size presets."""

    XS = QSize(12, 12)
    SM = QSize(16, 16)
    BASE = QSize(20, 20)
    MD = QSize(24, 24)
    LG = QSize(32, 32)
    XL = QSize(48, 48)
    XXL = QSize(64, 64)


class IconService(QObject):
    """
    Unified icon management service.

    Features:
    - Enum-based icon access (recommended)
    - Legacy string path support
    - Theme-aware resolution
    - Application-level caching
    - Size presets
    - Opacity/state handling

    Usage:
        icon_service = get_icon_service()

        # Using enums (preferred)
        icon = icon_service.get_icon(Icons.DASHBOARD)
        pixmap = icon_service.get_pixmap(Icons.SETTINGS, IconSize.LG)

        # Device icons
        device_icon = icon_service.get_device_icon("ACL")

        # With opacity (for disabled states)
        disabled_pixmap = icon_service.get_pixmap_with_opacity(Icons.SAVE, 0.5)
    """

    # Emitted when icons should be refreshed (theme change)
    iconsInvalidated = Signal()

    def __init__(self, theme_service: "ThemeService"):
        super().__init__()
        self._theme_service = theme_service
        self._provider = get_icon_provider(theme_service)

        # Opacity cache: (path, width, height, opacity) -> QPixmap
        self._opacity_cache: Dict[tuple, QPixmap] = {}

        # Connect to theme changes (FIXED: use correct signal name)
        theme_service.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change - clear opacity cache."""
        self._opacity_cache.clear()
        self.iconsInvalidated.emit()
        logger.debug(f"[IconService] Theme changed to {theme}, caches invalidated")

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
            size: Desired size (default: IconSize.MD)

        Returns:
            Theme-appropriate QPixmap (cached)
        """
        size = size or IconSize.MD
        return self._provider.get_pixmap(icon, size)

    def get_path(self, icon: Union[Icons, DeviceIcons, str]) -> str:
        """
        Get resolved resource path for the given icon.

        Args:
            icon: Icon enum or legacy string path

        Returns:
            Theme-appropriate resource path string
        """
        return self._provider.resolve_path(icon)

    # =========================================================================
    # Extended API - State Handling
    # =========================================================================

    def get_pixmap_with_opacity(self, icon: Union[Icons, DeviceIcons, str], opacity: float, size: Optional[QSize] = None) -> QPixmap:
        """
        Get QPixmap with custom opacity (for disabled/inactive states).

        Args:
            icon: Icon enum or legacy string path
            opacity: Opacity value (0.0 to 1.0)
            size: Desired size

        Returns:
            QPixmap with applied opacity
        """
        size = size or IconSize.MD
        path = self._provider.resolve_path(icon)
        cache_key = (path, size.width(), size.height(), opacity)

        if cache_key not in self._opacity_cache:
            base_pixmap = self._provider.get_pixmap(icon, size)

            if opacity >= 1.0:
                self._opacity_cache[cache_key] = base_pixmap
            else:
                # Create transparent pixmap
                result = QPixmap(base_pixmap.size())
                result.fill(QColor(0, 0, 0, 0))

                painter = QPainter(result)
                painter.setOpacity(opacity)
                painter.drawPixmap(0, 0, base_pixmap)
                painter.end()

                self._opacity_cache[cache_key] = result

        return self._opacity_cache[cache_key]

    def get_disabled_pixmap(self, icon: Union[Icons, DeviceIcons, str], size: Optional[QSize] = None) -> QPixmap:
        """
        Get disabled state pixmap (50% opacity).

        Args:
            icon: Icon enum or legacy string path
            size: Desired size

        Returns:
            QPixmap with disabled appearance
        """
        return self.get_pixmap_with_opacity(icon, 0.5, size)

    def get_hover_pixmap(self, icon: Union[Icons, DeviceIcons, str], size: Optional[QSize] = None) -> QPixmap:
        """
        Get hover state pixmap (slightly brighter).

        For SVGs, this just returns the normal pixmap.
        For more control, use tinted icons.

        Args:
            icon: Icon enum or legacy string path
            size: Desired size

        Returns:
            QPixmap for hover state
        """
        # For now, just return normal pixmap
        # Could be enhanced with brightness adjustment
        return self.get_pixmap(icon, size)

    # =========================================================================
    # Device-specific API
    # =========================================================================

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get QIcon for a device by equipment code."""
        return self._provider.get_device_icon(equipment_code)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get QPixmap for a device by equipment code."""
        return self._provider.get_device_pixmap(equipment_code, size)

    def has_device_icon(self, equipment_code: str) -> bool:
        """Check if a device icon exists for the given code."""
        return DeviceIcons.from_code(equipment_code) is not None

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def preload_navigation_icons(self) -> int:
        """
        Preload all navigation icons for fast startup.

        Returns:
            Number of icons preloaded
        """
        nav_icons = Icons.by_category(IconCategory.NAVIGATION)
        self._provider.preload(nav_icons)
        logger.info(f"[IconService] Preloaded {len(nav_icons)} navigation icons")
        return len(nav_icons)

    def preload_action_icons(self) -> int:
        """Preload all action icons."""
        action_icons = Icons.by_category(IconCategory.ACTION)
        self._provider.preload(action_icons)
        return len(action_icons)

    def preload_device_icons(self, codes: List[str]) -> int:
        """
        Preload device icons for specific equipment codes.

        Args:
            codes: List of equipment codes

        Returns:
            Number of icons preloaded
        """
        device_icons = [DeviceIcons.from_code(code) for code in codes if DeviceIcons.from_code(code)]
        if device_icons:
            self._provider.preload(device_icons)
        logger.info(f"[IconService] Preloaded {len(device_icons)} device icons")
        return len(device_icons)

    def preload_all(self) -> int:
        """
        Preload all icons.

        Returns:
            Total number of icons preloaded
        """
        count = 0

        # All Icons enum
        self._provider.preload(list(Icons))
        count += len(Icons)

        # All DeviceIcons enum
        self._provider.preload(list(DeviceIcons))
        count += len(DeviceIcons)

        logger.info(f"[IconService] Preloaded {count} total icons")
        return count

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    @property
    def cache_stats(self) -> Dict[str, int]:
        """Get icon cache statistics."""
        stats = self._provider.cache_stats.copy()
        stats["opacity_cache_size"] = len(self._opacity_cache)
        return stats

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._provider.clear_cache()
        self._opacity_cache.clear()
        logger.debug("[IconService] All caches cleared")

    @staticmethod
    def get_all_device_codes() -> List[str]:
        """Get all available device codes."""
        return sorted(DeviceIcons.all_codes())

    @staticmethod
    def get_icons_by_category(category: IconCategory) -> List[Icons]:
        """Get all icons in a category."""
        return Icons.by_category(category)


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


def create_icon_service(theme_service: "ThemeService") -> IconService:
    """Create a new IconService instance (for testing)."""
    return IconService(theme_service)


__all__ = [
    "IconService",
    "IconSize",
    "get_icon_service",
    "create_icon_service",
    "Icons",
    "DeviceIcons",
    "IconCategory",
]
