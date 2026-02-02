# File: presentation/resources/icons/provider.py
"""
Icon Provider - Application-level icon caching.

Responsibilities:
- Load and cache QIcon/QPixmap instances
- Resolve theme-appropriate paths
- Invalidate cache on theme change
- Provide fallbacks for missing icons
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

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
    - Fallback handling for missing icons
    - Backward compatible with string paths
    """

    # Default sizes
    DEFAULT_SIZE = QSize(24, 24)
    SMALL_SIZE = QSize(16, 16)
    LARGE_SIZE = QSize(32, 32)

    # Pattern to detect theme suffix
    _THEME_SUFFIX_PATTERN = re.compile(r"-white\.(svg|png)$")

    # Pattern to extract base name from resource path
    _RESOURCE_PATH_PATTERN = re.compile(r"^:?/?icon/(?:devices/)?(.+?)(?:-white)?\.(svg|png)$")

    def __init__(self, theme_service: "ThemeService"):
        self._theme_service = theme_service

        # Cache: resolved_path -> QIcon
        self._icon_cache: Dict[str, QIcon] = {}

        # Pixmap cache: (resolved_path, width, height) -> QPixmap
        self._pixmap_cache: Dict[Tuple[str, int, int], QPixmap] = {}

        # Track theme for cache invalidation
        self._cached_theme: str = theme_service.current_theme

        # Track failed loads to avoid repeated attempts
        self._failed_paths: set = set()

        # Connect to theme changes
        theme_service.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, new_theme: str) -> None:
        """Clear caches when theme changes."""
        if new_theme != self._cached_theme:
            icon_count = len(self._icon_cache)
            pixmap_count = len(self._pixmap_cache)

            self._icon_cache.clear()
            self._pixmap_cache.clear()
            self._failed_paths.clear()
            self._cached_theme = new_theme

            logger.debug(f"[IconProvider] Theme changed to {new_theme}, " f"cleared {icon_count} icons and {pixmap_count} pixmaps")

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    # =========================================================================
    # Path Resolution
    # =========================================================================

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
        return definition.get_path(self.is_dark)

    def _resolve_legacy_path(self, path: str) -> str:
        """
        Resolve legacy string path (backward compatibility).

        Handles various input formats:
        - ":/icon/dashboard.svg"
        - ":/icon/dashboard-white.svg"
        - "dashboard"
        - "/icon/devices/ACL.svg"
        """
        # Strip existing theme suffix for normalization
        if self._THEME_SUFFIX_PATTERN.search(path):
            path = self._THEME_SUFFIX_PATTERN.sub(r".\1", path)

        # Try to match to known enum first
        match = self._RESOURCE_PATH_PATTERN.match(path)
        if match:
            base_name = match.group(1)
            ext = match.group(2)

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

    # =========================================================================
    # Icon Loading
    # =========================================================================

    def get_icon(self, icon: Union[Icons, DeviceIcons, str]) -> QIcon:
        """
        Get cached QIcon for the given icon.

        Args:
            icon: Icon enum or legacy path string

        Returns:
            Cached QIcon instance (may be null if load failed)
        """
        path = self.resolve_path(icon)

        if path in self._icon_cache:
            return self._icon_cache[path]

        # Try to load
        qicon = QIcon(path)

        if qicon.isNull():
            if path not in self._failed_paths:
                logger.warning(f"[IconProvider] Failed to load icon: {path}")
                self._failed_paths.add(path)

            # Try fallback
            fallback = self._get_fallback_icon(icon)
            if fallback and not fallback.isNull():
                self._icon_cache[path] = fallback
                return fallback

        self._icon_cache[path] = qicon
        return qicon

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

        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        qicon = self.get_icon(icon)
        pixmap = qicon.pixmap(size)
        self._pixmap_cache[cache_key] = pixmap
        return pixmap

    def _get_fallback_icon(self, icon: Union[Icons, DeviceIcons, str]) -> Optional[QIcon]:
        """Get fallback icon for missing icons."""
        # For device icons, use logo as fallback
        if isinstance(icon, DeviceIcons):
            logo_path = Icons.LOGO.value.light_path
            return QIcon(logo_path)

        return None

    # =========================================================================
    # Device Icons
    # =========================================================================

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get icon for a device by equipment code."""
        device_icon = DeviceIcons.from_code(equipment_code)
        if device_icon:
            return self.get_icon(device_icon)

        logger.warning(f"[IconProvider] Unknown device code: {equipment_code}")
        return self.get_icon(Icons.LOGO)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get pixmap for a device by equipment code."""
        device_icon = DeviceIcons.from_code(equipment_code)
        if device_icon:
            return self.get_pixmap(device_icon, size)
        return self.get_pixmap(Icons.LOGO, size)

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def preload(self, icons: List[Union[Icons, DeviceIcons]]) -> int:
        """
        Preload icons into cache for faster access.

        Args:
            icons: List of icons to preload

        Returns:
            Number of icons successfully loaded
        """
        loaded = 0
        for icon in icons:
            qicon = self.get_icon(icon)
            if not qicon.isNull():
                loaded += 1

        logger.debug(f"[IconProvider] Preloaded {loaded}/{len(icons)} icons")
        return loaded

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._icon_cache.clear()
        self._pixmap_cache.clear()
        self._failed_paths.clear()
        logger.debug("[IconProvider] All caches cleared")

    # =========================================================================
    # Statistics
    # =========================================================================

    @property
    def cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "icon_cache_size": len(self._icon_cache),
            "pixmap_cache_size": len(self._pixmap_cache),
            "failed_paths": len(self._failed_paths),
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


def create_icon_provider(theme_service: "ThemeService") -> IconProvider:
    """Create a new IconProvider instance (for testing)."""
    return IconProvider(theme_service)


__all__ = [
    "IconProvider",
    "get_icon_provider",
    "create_icon_provider",
]
