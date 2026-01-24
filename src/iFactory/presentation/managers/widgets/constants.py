"""
Widget Constants - Unified UI Constants.

Merged from OLD system with NEW architecture compatibility.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Final, FrozenSet, List
from PySide6.QtCore import QSize


class IconSize(IntEnum):
    """Standard icon sizes."""

    SMALL = 16
    MEDIUM = 24
    LARGE = 30
    XLARGE = 48


class MenuDimension(IntEnum):
    """Menu dimension constants."""

    ITEM_HEIGHT = 40
    WIDTH_EXPANDED = 250
    WIDTH_COLLAPSED = 50


class RightPanelDimension(IntEnum):
    """Right panel dimension constants."""

    WIDTH_EXPANDED = 350
    WIDTH_COLLAPSED = 0
    WIDTH_MIN = 300
    WIDTH_MAX = 600
    HOVER_ZONE_WIDTH = 25


class TimerInterval(IntEnum):
    """Timer intervals in milliseconds."""

    THEME_HIDE = 150
    RIGHT_HOVER = 800
    POSITION_UPDATE = 10
    DEVICE_UPDATE = 50
    INIT_DELAY = 100
    GANTT_INIT = 300
    ANIMATION_DURATION = 200


@dataclass(frozen=True, slots=True)
class WindowConstants:
    """
    Immutable window-related constants.

    Aggregates all UI dimension and timing constants for easy access.
    """

    ICON_SIZE: QSize = field(default_factory=lambda: QSize(IconSize.LARGE, IconSize.LARGE))
    MENU_ITEM_HEIGHT: int = MenuDimension.ITEM_HEIGHT
    MENU_WIDTH_EXPANDED: int = MenuDimension.WIDTH_EXPANDED
    MENU_WIDTH_COLLAPSED: int = MenuDimension.WIDTH_COLLAPSED
    RIGHT_PANEL_WIDTH_EXPANDED: int = RightPanelDimension.WIDTH_EXPANDED
    RIGHT_PANEL_WIDTH_COLLAPSED: int = RightPanelDimension.WIDTH_COLLAPSED
    RIGHT_PANEL_WIDTH_MIN: int = RightPanelDimension.WIDTH_MIN
    RIGHT_PANEL_WIDTH_MAX: int = RightPanelDimension.WIDTH_MAX
    RIGHT_HOVER_ZONE_WIDTH: int = RightPanelDimension.HOVER_ZONE_WIDTH
    ANIMATION_DURATION: int = TimerInterval.ANIMATION_DURATION
    TIMER_THEME_HIDE: int = TimerInterval.THEME_HIDE
    TIMER_RIGHT_HOVER: int = TimerInterval.RIGHT_HOVER
    TIMER_POSITION_UPDATE: int = TimerInterval.POSITION_UPDATE
    TIMER_DEVICE_UPDATE: int = TimerInterval.DEVICE_UPDATE
    TIMER_INIT_DELAY: int = TimerInterval.INIT_DELAY
    TIMER_GANTT_INIT: int = TimerInterval.GANTT_INIT


class Sizes:
    """Widget dimension constants (simple access)."""

    MENU_BTN_H: Final[int] = MenuDimension.ITEM_HEIGHT
    MENU_ICON: Final[int] = IconSize.MEDIUM
    MENU_ICON_PAD: Final[int] = 5
    PANEL_MIN_W: Final[int] = RightPanelDimension.WIDTH_MIN
    PANEL_MAX_W: Final[int] = RightPanelDimension.WIDTH_MAX
    PANEL_DEF_W: Final[int] = RightPanelDimension.WIDTH_EXPANDED
    HANDLE_W: Final[int] = 6
    TOGGLE_W: Final[int] = 16
    TOGGLE_H: Final[int] = 40
    ARROW_ICON: Final[int] = IconSize.LARGE
    SETTINGS_W: Final[int] = 220
    THEME_W: Final[int] = 100
    TABLE_ROW_H: Final[int] = 28
    TABLE_HEADER_H: Final[int] = 32


class Timing:
    """Animation/debounce timing constants (milliseconds)."""

    HOVER: Final[int] = TimerInterval.RIGHT_HOVER
    LEAVE: Final[int] = TimerInterval.THEME_HIDE
    ANIM: Final[int] = TimerInterval.ANIMATION_DURATION
    DEBOUNCE: Final[int] = TimerInterval.POSITION_UPDATE


class Icons:
    """Icon resource path constants."""

    ARROW_OPEN: Final[str] = ":/icon/arrow_menu_open.svg"
    ARROW_CLOSE: Final[str] = ":/icon/arrow_menu_close.svg"
    EXPAND: Final[str] = ":/icon/expand.svg"
    CLOSE: Final[str] = ":/icon/close.svg"
    SETTINGS: Final[str] = ":/icon/settings.svg"
    LOGO: Final[str] = ":/icon/logo.png"
    OPEN: Final[str] = ":/icon/open.svg"


PAGE_MAPPING: Final[Dict[str, str]] = {
    "Dashboard": "daboard_page",
    "Orders": "orders_page",
    "Products": "products_page",
    "Customers": "customers_page",
    "Reports": "reports_page",
}
DEVICE_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_midle_frame_1", "orders_midle_frame_1"})
GANTT_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_midle_frame_2", "orders_midle_frame_2"})
LEGEND_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_bottom_frame", "orders_bottom_frame"})
DEVICE_FRAMES_LIST: Final[List[str]] = list(DEVICE_FRAMES)
GANTT_FRAMES_LIST: Final[List[str]] = list(GANTT_FRAMES)
LEGEND_FRAMES_LIST: Final[List[str]] = list(LEGEND_FRAMES)
GANTT_PAGE_MAPPING: Final[Dict[str, str]] = {
    "daboard_page": "daboard_midle_frame_2",
    "orders_page": "orders_midle_frame_2",
}


@dataclass(frozen=True, slots=True)
class DefaultGanttDevices:
    """Default device assignments for Gantt charts."""

    dashboard: str = "AMX01"
    orders: str = "CWD01"

    def to_frame_mapping(self) -> Dict[str, str]:
        """Convert to frame-device mapping."""
        return {
            "daboard_midle_frame_2": self.dashboard,
            "orders_midle_frame_2": self.orders,
        }


class HistoryType:
    """History type constants."""

    STATUS: Final[str] = "status"
    INPUT: Final[str] = "input"
    OUTPUT: Final[str] = "output"
    SUMMARY: Final[str] = "summary"
    ALL: Final[FrozenSet[str]] = frozenset({STATUS, INPUT, OUTPUT})
    DISPLAY_NAMES: Final[Dict[str, str]] = {
        STATUS: "Status",
        INPUT: "Input",
        OUTPUT: "Output",
        SUMMARY: "Summary",
    }
    ICONS: Final[Dict[str, str]] = {
        STATUS: "📋",
        INPUT: "📥",
        OUTPUT: "📤",
        SUMMARY: "📊",
    }

    @classmethod
    def get_display_name(cls, history_type: str) -> str:
        return cls.DISPLAY_NAMES.get(history_type, "History")

    @classmethod
    def get_icon(cls, history_type: str) -> str:
        return cls.ICONS.get(history_type, "📄")


STATUS_COLORS: Final[Dict[str, str]] = {
    "running": "#4CAF50",
    "shutdown": "#9E9E9E",
    "stop": "#FFC107",
    "maintenance": "#2196F3",
    "alarm": "#F44336",
    "idle": "#FF9800",
    "error": "#F44336",
    "unknown": "#757575",
}
DISPLAY_STATUS_MAP: Final[Dict[str, str]] = {
    "Running": "running",
    "Shutdown": "shutdown",
    "Stop": "stop",
    "Maintenance": "maintenance",
    "Alarm": "alarm",
    "Idle": "idle",
    "Error": "error",
}
CONTEXT_MENU_STYLESHEET: Final[str] = (
    "\nQMenu {\n    background: palette(window);\n    border: 1px solid palette(mid);\n    padding: 4px;\n    border-radius: 4px;\n}\nQMenu::item {\n    padding: 8px 24px 8px 16px;\n    border-radius: 2px;\n}\nQMenu::item:selected {\n    background: palette(highlight);\n    color: palette(highlighted-text);\n}\nQMenu::separator {\n    height: 1px;\n    background: palette(mid);\n    margin: 4px 8px;\n}\n"
)


@dataclass(frozen=True, slots=True)
class ShortcutKey:
    """Keyboard shortcut key constants."""

    ESCAPE: str = "Escape"
    FULLSCREEN: str = "F11"
    INFO: str = "F1"
    NEXT_PAGE: str = "Ctrl+Tab"
    PREV_PAGE: str = "Ctrl+Shift+Tab"
    TOGGLE_THEME: str = "Ctrl+Shift+T"
    TOGGLE_LEFT_MENU: str = "Ctrl+L"
    TOGGLE_RIGHT_MENU: str = "Ctrl+R"
    SETTINGS: str = "Ctrl+,"
    EDIT_MODE: str = "Ctrl+E"


class Shortcuts:
    """Keyboard shortcuts documentation and constants."""

    KEYS: Final = ShortcutKey()
    INFO_TEXT: Final[str] = (
        "\nAES Lithium Battery\nDesigned by Industrial Engineering Team\n\nKeyboard Shortcuts:\n─────────────────────\nF11                  Toggle Fullscreen\nCtrl+Tab             Next Page\nCtrl+Shift+Tab       Previous Page\nCtrl+1~5             Go to Page\nCtrl+L               Toggle Left Menu\nCtrl+R               Toggle Right Menu\nCtrl+,               Settings\nCtrl+Shift+T         Toggle Theme\nCtrl+E               Edit Device Positions\nF1                   Information\nEsc                  Close/Exit\n"
    )

    @classmethod
    def get_shortcut_list(cls) -> List[tuple[str, str]]:
        return [
            ("F11", "Toggle Fullscreen"),
            ("Ctrl+Tab", "Next Page"),
            ("Ctrl+Shift+Tab", "Previous Page"),
            ("Ctrl+1~5", "Go to Page"),
            ("Ctrl+L", "Toggle Left Menu"),
            ("Ctrl+R", "Toggle Right Menu"),
            ("Ctrl+,", "Settings"),
            ("Ctrl+Shift+T", "Toggle Theme"),
            ("Ctrl+E", "Edit Device Positions"),
            ("F1", "Information"),
            ("Esc", "Close/Exit"),
        ]


__all__ = [
    "IconSize",
    "MenuDimension",
    "RightPanelDimension",
    "TimerInterval",
    "WindowConstants",
    "Sizes",
    "Timing",
    "Icons",
    "PAGE_MAPPING",
    "DEVICE_FRAMES",
    "GANTT_FRAMES",
    "LEGEND_FRAMES",
    "DEVICE_FRAMES_LIST",
    "GANTT_FRAMES_LIST",
    "LEGEND_FRAMES_LIST",
    "GANTT_PAGE_MAPPING",
    "DefaultGanttDevices",
    "HistoryType",
    "STATUS_COLORS",
    "DISPLAY_STATUS_MAP",
    "CONTEXT_MENU_STYLESHEET",
    "ShortcutKey",
    "Shortcuts",
]
