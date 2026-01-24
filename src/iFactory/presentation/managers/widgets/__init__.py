"""
UI Widgets Package - Presentation Layer (Qt)

Safe imports with fallback handling for optional components.
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)
_available: Dict[str, Any] = {}
_errors: List[str] = []


def _safe_import(name: str, module_path: str, symbols: List[str]) -> None:
    """Safely import symbols from a module."""
    global _available, _errors
    try:
        module = __import__(module_path, fromlist=symbols)
        for sym in symbols:
            obj = getattr(module, sym, None)
            if obj is not None:
                _available[sym] = obj
                globals()[sym] = obj
            else:
                _errors.append(f"{sym} not found in {module_path}")
    except Exception as e:
        _errors.append(f"{module_path}: {e}")


_safe_import("constants", "iFactory.ui.widgets.constants", ["Sizes", "Timing", "Icons", "STATUS_COLORS", "DISPLAY_STATUS_MAP"])
_safe_import("menu_widgets", "iFactory.ui.widgets.menu_widgets", ["MenuDelegate", "HoverWidget", "ExpandableMenuButton", "MenuButtonWithShortcut"])
_safe_import("panel_widgets", "iFactory.ui.widgets.panel_widgets", ["ClickCatcher", "SettingsRootPanel", "ThemeSubPanel"])
_safe_import(
    "gantt", "iFactory.presentation.managers.widgets.gantt", ["GanttStrip", "GanttThemeProvider", "format_duration"]
)
_safe_import(
    "right_slide_menu",
    "iFactory.ui.widgets.right_slide_menu",
    ["RightSlideMenuWidget", "StatusSummaryRow", "InputHistoryRow", "SummaryRow", "SummaryTableWidget", "ViewMode"],
)
_safe_import("gantt", "iFactory.ui.widgets.gantt", ["GanttStrip", "GanttThemeProvider", "format_duration"])
_safe_import(
    "device_widget", "iFactory.ui.widgets.device_widget", ["IndividualDeviceWidget", "IndividualDeviceWidgetFactory", "IndividualDeviceData"]
)
if "GanttThemeProvider" in _available:
    ThemeProvider = _available["GanttThemeProvider"]
    _available["ThemeProvider"] = ThemeProvider
if "Sizes" in _available:
    WidgetSizes = _available["Sizes"]
    _available["WidgetSizes"] = WidgetSizes
if "Timing" in _available:
    TimingConstants = _available["Timing"]
    _available["TimingConstants"] = TimingConstants
if "Icons" in _available:
    IconPaths = _available["Icons"]
    _available["IconPaths"] = IconPaths
if "IndividualDeviceWidget" in _available:
    DeviceWidget = _available["IndividualDeviceWidget"]
    _available["DeviceWidget"] = DeviceWidget
    globals()["DeviceWidget"] = DeviceWidget
if "IndividualDeviceWidgetFactory" in _available:
    DeviceWidgetFactory = _available["IndividualDeviceWidgetFactory"]
    _available["DeviceWidgetFactory"] = DeviceWidgetFactory
    globals()["DeviceWidgetFactory"] = DeviceWidgetFactory
if "IndividualDeviceData" in _available:
    DeviceData = _available["IndividualDeviceData"]
    _available["DeviceData"] = DeviceData
    globals()["DeviceData"] = DeviceData
if _errors:
    logger.debug(f"Widget import errors ({len(_errors)}): {_errors[:3]}")
else:
    logger.debug(f"Widgets loaded: {len(_available)} symbols")
__all__ = list(_available.keys())
