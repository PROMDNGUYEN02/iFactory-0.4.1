# File: presentation/views/widgets/__init__.py
"""
Widget components for the presentation layer.

All widgets accept ThemeService via constructor injection.
"""

from .device_canvas import DeviceCanvasWidget
from .gantt_canvas import (
    GanttCanvasWidget,
    DeviceGanttWidget,
    AnimatedProgressBar,
    CompactStatCard,
    SingleDeviceGanttBar,
    STATUS_GRADIENTS,
)
from .device_gantt_widget import DeviceGanttDisplayWidget
from .legend_widget import LegendWidget

__all__ = [
    # Canvas
    "DeviceCanvasWidget",
    # Gantt
    "GanttCanvasWidget",
    "DeviceGanttWidget",
    "DeviceGanttDisplayWidget",
    "AnimatedProgressBar",
    "CompactStatCard",
    "SingleDeviceGanttBar",
    "STATUS_GRADIENTS",
    # Legend
    "LegendWidget",
]
