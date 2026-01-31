# File: presentation/constants/layout.py
from typing import Final


class Layout:
    SIDEBAR_COLLAPSED_WIDTH: Final[int] = 60
    SIDEBAR_EXPANDED_WIDTH: Final[int] = 200
    RIGHT_PANEL_COLLAPSED_WIDTH: Final[int] = 0
    RIGHT_PANEL_EXPANDED_WIDTH: Final[int] = 350
    HEADER_HEIGHT: Final[int] = 40
    STATUS_BAR_HEIGHT: Final[int] = 24
    GANTT_ROW_HEIGHT: Final[int] = 32
    GANTT_COMPACT_ROW_HEIGHT: Final[int] = 20
    LEGEND_HEIGHT: Final[int] = 60


__all__ = ["Layout"]
