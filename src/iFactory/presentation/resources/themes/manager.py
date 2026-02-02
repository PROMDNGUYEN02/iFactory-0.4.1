# File: presentation/resources/themes/manager.py
"""
Theme Manager - Backward Compatibility Layer.

DEPRECATED: Use presentation.services.theme_service.ThemeService instead.

This class delegates to ThemeService for backward compatibility.
"""

from __future__ import annotations

import logging
import warnings
from typing import Optional

from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class ThemeManager:
    """
    DEPRECATED: Use ThemeService instead.

    This class is a thin wrapper around ThemeService for backward compatibility.
    """

    _instance: Optional["ThemeManager"] = None

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Delegate to ThemeService
        from ...services.theme_service import get_theme_service

        self._theme_service = get_theme_service()
        self._initialized = True

    def set_theme(self, theme: str) -> None:
        """Set current theme."""
        self._theme_service.set_theme(theme)

    @property
    def current_theme(self) -> str:
        """Get current theme name."""
        return self._theme_service.current_theme

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    def get_color(self, key: str) -> str:
        """Get color by key."""
        return self._theme_service.get_color(key)

    def get_qcolor(self, key: str) -> QColor:
        """Get color as QColor."""
        return self._theme_service.get_qcolor(key)

    def get_icon_path(self, original_path: str) -> str:
        """Get themed icon path."""
        return self._theme_service.get_icon_path(original_path)

    def get_stylesheet(self) -> str:
        """Get compiled stylesheet."""
        return self._theme_service.get_stylesheet()


_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """
    Get the global ThemeManager instance.

    DEPRECATED: Use get_theme_service() from presentation.services.theme_service instead.
    """
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance


__all__ = ["ThemeManager", "get_theme_manager"]
