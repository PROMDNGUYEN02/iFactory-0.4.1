"""
Color Registry - Flyweight Pattern for Qt drawing objects.

Pre-creates and caches all QColor, QBrush, QPen objects to avoid
per-frame allocation in paintEvent.

CRITICAL: Never create QColor/QBrush/QPen inside paintEvent!
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen


class ColorRegistry:
    """
    Singleton registry for cached Qt drawing objects.

    Usage:
        colors = ColorRegistry.instance()
        brush = colors.get_brush("#2ECC71")
        pen = colors.get_pen("#E74C3C", width=2)
    """

    _instance: Optional["ColorRegistry"] = None

    # Pre-defined status colors
    STATUS_COLORS: Dict[int, str] = {
        0: "transparent",
        1: "#2ECC71",
        2: "#7F8C8D",
        3: "#E74C3C",
        4: "#9B59B6",
        5: "#F1C40F",
    }

    STATUS_GRADIENTS: Dict[int, Tuple[str, str]] = {
        0: ("transparent", "transparent"),
        1: ("#34D399", "#059669"),
        2: ("#94A3B8", "#64748B"),
        3: ("#F87171", "#DC2626"),
        4: ("#A78BFA", "#7C3AED"),
        5: ("#FBBF24", "#D97706"),
    }

    @classmethod
    def instance(cls) -> "ColorRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._colors: Dict[str, QColor] = {}
        self._brushes: Dict[str, QBrush] = {}
        self._pens: Dict[Tuple[str, float, int], QPen] = {}
        self._fonts: Dict[Tuple[str, int, int], QFont] = {}

        self._preload_status_colors()

    def _preload_status_colors(self) -> None:
        """Pre-load all status colors."""
        for color in self.STATUS_COLORS.values():
            self.get_color(color)
            self.get_brush(color)

        for start, end in self.STATUS_GRADIENTS.values():
            self.get_color(start)
            self.get_color(end)

    def get_color(self, color_str: str) -> QColor:
        """Get cached QColor."""
        key = color_str.lower()
        if key not in self._colors:
            if key == "transparent":
                self._colors[key] = QColor(Qt.GlobalColor.transparent)
            else:
                self._colors[key] = QColor(color_str)
        return self._colors[key]

    def get_brush(self, color_str: str) -> QBrush:
        """Get cached QBrush."""
        key = color_str.lower()
        if key not in self._brushes:
            self._brushes[key] = QBrush(self.get_color(color_str))
        return self._brushes[key]

    def get_pen(self, color_str: str, width: float = 1.0, style: int = Qt.PenStyle.SolidLine) -> QPen:
        """Get cached QPen."""
        key = (color_str.lower(), width, style)
        if key not in self._pens:
            pen = QPen(self.get_color(color_str))
            pen.setWidthF(width)
            pen.setStyle(Qt.PenStyle(style))
            self._pens[key] = pen
        return self._pens[key]

    def get_font(self, family: str = "Segoe UI", size: int = 9, weight: int = QFont.Weight.Normal) -> QFont:
        """Get cached QFont."""
        key = (family, size, weight)
        if key not in self._fonts:
            font = QFont(family, size)
            font.setWeight(QFont.Weight(weight))
            self._fonts[key] = font
        return self._fonts[key]

    def get_status_color(self, status_code: int) -> QColor:
        """Get cached status color."""
        color_str = self.STATUS_COLORS.get(status_code, "transparent")
        return self.get_color(color_str)

    def get_status_brush(self, status_code: int) -> QBrush:
        """Get cached status brush."""
        color_str = self.STATUS_COLORS.get(status_code, "transparent")
        return self.get_brush(color_str)

    def get_status_gradient_colors(self, status_code: int) -> Tuple[QColor, QColor]:
        """Get cached gradient colors for status."""
        start, end = self.STATUS_GRADIENTS.get(status_code, ("transparent", "transparent"))
        return self.get_color(start), self.get_color(end)

    def clear_cache(self) -> None:
        """Clear all caches (for theme changes)."""
        self._colors.clear()
        self._brushes.clear()
        self._pens.clear()
        self._preload_status_colors()


def get_color_registry() -> ColorRegistry:
    """Get singleton ColorRegistry instance."""
    return ColorRegistry.instance()


__all__ = [
    "ColorRegistry",
    "get_color_registry",
]
