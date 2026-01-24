"""
Presentation Managers Package.

This package aggregates utility classes responsible for managing
various aspects of the User Interface (UI).

Components:
    - Resource Managers: Handle themes and icon assets (ThemeManager, IconManager).
    - UI Managers: Orchestrate complex UI interactions like animations,
                  layouts, panels, and keyboard shortcuts (AnimationManager,
                  MenuManager, PanelManager, ShortcutManager).
"""

from .icon_manager import IconConfig, IconManager
from .theme_manager import ThemeManager
from .ui_managers import (
    AnimationManager,
    AnimationTarget,
    MenuManager,
    PanelManager,
    RightPanelManager,
    ShortcutManager,
    ShortcutDefinition,
    create_standard_shortcuts,
)

__all__ = [
    "ThemeManager",
    "IconManager",
    "IconConfig",
    "AnimationManager",
    "AnimationTarget",
    "MenuManager",
    "PanelManager",
    "RightPanelManager",
    "ShortcutManager",
    "ShortcutDefinition",
    "create_standard_shortcuts",
]
