# File: presentation/resources/icons/resolver.py
"""
Icon Resolver - Theme-aware path resolution.

Eliminates:
- Manual theme logic in views
- Inconsistent resolution rules
- String manipulation (appending "-white")
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional, Union

from .registry import Icons, DeviceIcons, IconDefinition

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class IconResolver:
    """
    Resolves icon paths based on current theme.

    Single Responsibility: Only handles path resolution logic.
    Does NOT load icons or cache them.
    """

    # Pattern to detect if path already has theme suffix
    _THEME_SUFFIX_PATTERN = re.compile(r"-white\.svg$")

    # Pattern to extract base name from resource path
    _RESOURCE_PATH_PATTERN = re.compile(r"^:?/?icon/(?:devices/)?(.+?)(?:-white)?\.svg$")

    def __init__(self, theme_service: "ThemeService"):
        self._theme_service = theme_service

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    def resolve(self, icon: Union[Icons, DeviceIcons, str]) -> str:
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
        definition = icon.definition

        if self.is_dark and definition.has_themed_variant:
            return definition.dark_path
        return definition.light_path

    def _resolve_legacy_path(self, path: str) -> str:
        """
        Resolve legacy string path (backward compatibility).

        Handles various input formats:
        - ":/icon/electrode.svg"
        - ":/icon/electrode-white.svg"
        - "electrode"
        - "/icon/devices/ACL.svg"
        """
        # Already has white suffix - strip it first for normalization
        if self._THEME_SUFFIX_PATTERN.search(path):
            path = self._THEME_SUFFIX_PATTERN.sub(".svg", path)

        # Try to match to enum first
        match = self._RESOURCE_PATH_PATTERN.match(path)
        if match:
            base_name = match.group(1)

            # Try Icons enum
            for icon in Icons:
                if icon.definition.base_name == base_name:
                    return self._resolve_enum(icon)

            # Try DeviceIcons enum
            device_icon = DeviceIcons.from_code(base_name)
            if device_icon:
                return self._resolve_enum(device_icon)

        # Fallback: Apply theme suffix manually
        if self.is_dark:
            # Check if it looks like an SVG path
            if path.endswith(".svg"):
                return path.replace(".svg", "-white.svg")
            elif "." not in path.split("/")[-1]:
                # No extension, assume SVG
                return f":/icon/{path}-white.svg"

        # Light theme or unknown format
        if not path.startswith(":"):
            if "." not in path.split("/")[-1]:
                return f":/icon/{path}.svg"
            return f":/icon/{path}"

        return path

    def resolve_device(self, equipment_code: str) -> str:
        """
        Resolve device icon by equipment code.

        Args:
            equipment_code: Device equipment code (e.g., "ACL", "CBC")

        Returns:
            Resolved resource path
        """
        device_icon = DeviceIcons.from_code(equipment_code)
        if device_icon:
            return self._resolve_enum(device_icon)

        # Fallback for unknown devices
        logger.warning(f"Unknown device code: {equipment_code}, using fallback")
        if self.is_dark:
            return ":/icon/logo.png"  # Fallback icon
        return ":/icon/logo.png"


__all__ = ["IconResolver"]
