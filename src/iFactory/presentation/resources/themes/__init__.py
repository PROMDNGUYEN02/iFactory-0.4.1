# File: presentation/resources/themes/__init__.py
from .manager import ThemeManager, get_theme_manager

theme_manager = get_theme_manager()

__all__ = ["ThemeManager", "get_theme_manager", "theme_manager"]
