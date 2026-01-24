"""
Gantt Chart Widgets - Presentation Layer (Qt)

High-performance timeline visualization components.
"""

from __future__ import annotations
from .strip import GanttStrip
from .theme import GanttThemeProvider
from .utils import format_duration

ThemeProvider = GanttThemeProvider
__all__ = ["GanttStrip", "GanttThemeProvider", "ThemeProvider", "format_duration"]
