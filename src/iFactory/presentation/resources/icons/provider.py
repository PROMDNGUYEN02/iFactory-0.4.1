# File: presentation/resources/icons/provider.py
"""
Icon Provider - Application-level icon caching.

Eliminates:
- Redundant QIcon loading
- Per-widget icon instantiation
- Memory waste from duplicate icons
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Dict, Optional, Tuple, Union

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

from .registry import Icons, DeviceIcons, IconDefinition

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class IconProvider:
    """
    Centralized icon provider with caching.

    Features:
    - Application-level QIcon cache
    - Theme-aware icon resolution
    - Automatic cache invalidation on theme change
    - Size-specific pixmap caching
    - Backward compatible with string paths
    """

    # Default icon sizes
    DEFAULT_SIZE = QSize(24, 24)
    SMALL_SIZE = QSize(16, 16)
    LARGE_SIZE = QSize(32, 32)

    # Pattern to detect theme suffix
    _THEME_SUFFIX_PATTERN = re.compile(r"-white\.(svg|png)$")

    # Pattern to extract base name from resource path
    _RESOURCE_PATH_PATTERN = re.compile(r"^:?/?icon/(?:devices/)?(.+?)(?:-white)?\.(svg|png)$")

    def __init__(self, theme_service: "ThemeService"):
        self._theme_service = theme_service

        # Cache: (resolved_path) -> QIcon
        self._icon_cache: Dict[str, QIcon] = {}

        # Pixmap cache: (resolved_path, width, height) -> QPixmap
        self._pixmap_cache: Dict[Tuple[str, int, int], QPixmap] = {}

        # Track theme for cache invalidation
        self._cached_theme: str = theme_service.current_theme

        # Connect to theme changes
        theme_service.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, new_theme: str) -> None:
        """Clear caches when theme changes."""
        if new_theme != self._cached_theme:
            logger.debug(f"[IconProvider] Theme changed to {new_theme}, clearing {len(self._icon_cache)} cached icons")
            self._icon_cache.clear()
            self._pixmap_cache.clear()
            self._cached_theme = new_theme

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    def resolve_path(self, icon: Union[Icons, DeviceIcons, str]) -> str:
        """
        Resolve icon to theme-appropriate path.

        Args:
            icon: Icon enum or legacy string path

        Returns:
            Resolved resource path for current theme
        """
        if isinstance(icon, (Icons, DeviceIcons)):
            return self._resolve_enum(icon)
        else:
            return self._resolve_legacy_path(icon)

    def _resolve_enum(self, icon: Union[Icons, DeviceIcons]) -> str:
        """Resolve enum-based icon."""
        definition = icon.value

        if self.is_dark and definition.has_themed_variant:
            return definition.dark_path
        return definition.light_path

    def _resolve_legacy_path(self, path: str) -> str:
        """
        Resolve legacy string path (backward compatibility).

        Handles:
        - ":/icon/dashboard.svg"
        - ":/icon/dashboard-white.svg"
        - "dashboard"
        """
        # Strip existing theme suffix for normalization
        if self._THEME_SUFFIX_PATTERN.search(path):
            path = self._THEME_SUFFIX_PATTERN.sub(r".\1", path)

        # Try to match to known enum first
        match = self._RESOURCE_PATH_PATTERN.match(path)
        if match:
            base_name = match.group(1)

            # Try Icons enum
            for icon in Icons:
                if icon.value.base_name == base_name:
                    return self._resolve_enum(icon)

            # Try DeviceIcons enum
            device_icon = DeviceIcons.from_code(base_name)
            if device_icon:
                return self._resolve_enum(device_icon)

        # Fallback: Apply theme suffix manually
        if self.is_dark:
            if path.endswith(".svg"):
                return path.replace(".svg", "-white.svg")
            elif path.endswith(".png"):
                return path  # PNGs typically don't have themed variants
            elif "." not in path.split("/")[-1]:
                return f":/icon/{path}-white.svg"

        # Light theme or unknown format
        if not path.startswith(":"):
            if "." not in path.split("/")[-1]:
                return f":/icon/{path}.svg"
            return f":/icon/{path}"

        return path

    def get_icon(self, icon: Union[Icons, DeviceIcons, str]) -> QIcon:
        """
        Get cached QIcon for the given icon.

        Args:
            icon: Icon enum or legacy path string

        Returns:
            Cached QIcon instance
        """
        path = self.resolve_path(icon)

        if path not in self._icon_cache:
            qicon = QIcon(path)
            if qicon.isNull():
                logger.warning(f"[IconProvider] Failed to load icon: {path}")
            self._icon_cache[path] = qicon

        return self._icon_cache[path]

    def get_pixmap(self, icon: Union[Icons, DeviceIcons, str], size: Optional[QSize] = None) -> QPixmap:
        """
        Get cached QPixmap for the given icon and size.

        Args:
            icon: Icon enum or legacy path string
            size: Desired size (default: DEFAULT_SIZE)

        Returns:
            Cached QPixmap instance
        """
        size = size or self.DEFAULT_SIZE
        path = self.resolve_path(icon)
        cache_key = (path, size.width(), size.height())

        if cache_key not in self._pixmap_cache:
            qicon = self.get_icon(icon)
            pixmap = qicon.pixmap(size)
            self._pixmap_cache[cache_key] = pixmap

        return self._pixmap_cache[cache_key]

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get icon for a device by equipment code."""
        device_icon = DeviceIcons.from_code(equipment_code)
        if device_icon:
            return self.get_icon(device_icon)

        # Fallback for unknown devices
        logger.warning(f"[IconProvider] Unknown device code: {equipment_code}")
        return self.get_icon(Icons.LOGO)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get pixmap for a device by equipment code."""
        device_icon = DeviceIcons.from_code(equipment_code)
        if device_icon:
            return self.get_pixmap(device_icon, size)

        return self.get_pixmap(Icons.LOGO, size)

    def preload(self, icons: list) -> None:
        """Preload icons into cache for faster access."""
        for icon in icons:
            self.get_icon(icon)
        logger.debug(f"[IconProvider] Preloaded {len(icons)} icons")

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._icon_cache.clear()
        self._pixmap_cache.clear()
        logger.debug("[IconProvider] Cache cleared")

    @property
    def cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "icon_cache_size": len(self._icon_cache),
            "pixmap_cache_size": len(self._pixmap_cache),
        }


# Module-level singleton
_provider_instance: Optional[IconProvider] = None


def get_icon_provider(theme_service: Optional["ThemeService"] = None) -> IconProvider:
    """
    Get the global IconProvider instance.

    Args:
        theme_service: ThemeService instance (required on first call)

    Returns:
        Global IconProvider instance
    """
    global _provider_instance

    if _provider_instance is None:
        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()
        _provider_instance = IconProvider(theme_service)

    return _provider_instance


__all__ = ["IconProvider", "get_icon_provider"]
