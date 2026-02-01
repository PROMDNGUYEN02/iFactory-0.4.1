"""
Shell Views Package.

Shell components for the main application frame:
- HeaderView: Top bar with toggle and window controls
- SidebarView: Navigation sidebar
- RightPanelView: Device details panel
- StatusBarView: Bottom status bar
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
