# File: presentation/views/shell/__init__.py
"""
Shell Views - Application frame components.

These views make up the main application shell:
- HeaderView: Logo, title, toggle button
- SidebarView: Navigation menu
- RightPanelView: Device details panel
- StatusBarView: Connection status

All views use ThemeService for centralized theming.
"""

from .header import HeaderView
from .sidebar import SidebarView
from .right_panel import RightPanelView
from .status_bar import StatusBarView

__all__ = [
    "HeaderView",
    "SidebarView",
    "RightPanelView",
    "StatusBarView",
]
