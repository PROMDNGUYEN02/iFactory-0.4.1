# File: presentation/resources/themes/__init__.py
"""
Theme Resources - Backward Compatibility Layer.

DEPRECATED: Use presentation.services.theme_service instead.

This module provides backward compatibility for existing code.
"""

import warnings

from .manager import ThemeManager, get_theme_manager

# Lazy initialization for backward compatibility
_theme_manager = None


def _get_lazy_theme_manager():
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = get_theme_manager()
    return _theme_manager


# For code that imports `theme_manager` directly
class _LazyThemeManager:
    """Lazy proxy for theme_manager."""

    def __getattr__(self, name):
        return getattr(_get_lazy_theme_manager(), name)


theme_manager = _LazyThemeManager()

__all__ = ["ThemeManager", "get_theme_manager", "theme_manager"]
