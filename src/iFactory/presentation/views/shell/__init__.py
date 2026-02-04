# File: presentation/views/shell/__init__.py
"""
Shell Views - Application frame components.

These views make up the main application shell:
- HeaderView: Logo, title, toggle button
- SidebarView: Navigation menu
- RightPanelView: Device details panel
- StatusBarView: Connection status

All views follow MVVM pattern and use ThemeService for centralized theming.
"""

from .header import HeaderView
from .sidebar import SidebarView, NavButtonBase, ModernNavButton, SettingsButton
from .right_panel import RightPanelView, MaterialInputWidget
from .status_bar import StatusBarView, ConnectionIndicator, SystemModeLabel

__all__ = [
    # Main Views
    "HeaderView",
    "SidebarView",
    "RightPanelView",
    "StatusBarView",
    # Sidebar Components
    "NavButtonBase",
    "ModernNavButton",
    "SettingsButton",
    # Right Panel Components
    "MaterialInputWidget",
    # Status Bar Components
    "ConnectionIndicator",
    "SystemModeLabel",
]
