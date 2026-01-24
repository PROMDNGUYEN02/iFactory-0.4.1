"""
Gantt Theme Provider - Presentation Layer (Qt)

Centralized theme management for Gantt charts.
"""

from __future__ import annotations
from functools import lru_cache
from typing import ClassVar, Dict, Optional

__all__ = ["GanttThemeProvider"]


class GanttThemeProvider:
    """
    Provides theme colors for Gantt chart components.

    Supports light/dark themes with customizable colors.
    Uses LRU cache for performance.
    """

    __slots__ = ()
    _custom: ClassVar[Optional[Dict[str, Dict[str, str]]]] = None
    _DEFAULT: ClassVar[Dict[str, Dict[str, str]]] = {
        "light": {
            "surface": "#ffffff",
            "text": "#1a1a1a",
            "text_alt": "#666666",
            "primary": "#0078d4",
            "border": "#e0e0e0",
        },
        "dark": {
            "surface": "#1e1e1e",
            "text": "#ffffff",
            "text_alt": "#888888",
            "primary": "#0078d4",
            "border": "#3a3a3a",
        },
    }
    _STATUS: ClassVar[Dict[str, Dict[str, str]]] = {
        "light": {
            "running": "#4CAF50",
            "shutdown": "#9E9E9E",
            "stop": "#FFC107",
            "maintenance": "#2196F3",
            "alarm": "#F44336",
            "idle": "#FF9800",
            "error": "#F44336",
            "unknown": "#757575",
        },
        "dark": {
            "running": "#66BB6A",
            "shutdown": "#BDBDBD",
            "stop": "#FFCA28",
            "maintenance": "#42A5F5",
            "alarm": "#EF5350",
            "idle": "#FFA726",
            "error": "#EF5350",
            "unknown": "#9E9E9E",
        },
    }

    @classmethod
    def set_colors(cls, colors: Dict[str, Dict[str, str]]) -> None:
        """
        Set custom color overrides.

        Args:
            colors: Dictionary with theme colors, e.g.:
                {
                    "light": {"surface": "#fff", ...},
                    "dark": {"surface": "#000", ...}
                }
        """
        cls._custom = colors
        cls.get_status_color.cache_clear()
        cls.get_colors.cache_clear()

    @classmethod
    @lru_cache(maxsize=32)
    def get_status_color(cls, status: Optional[str], theme: str = "light") -> str:
        """
        Get color for status code.

        Args:
            status: Status code (e.g., "running", "stop")
            theme: Theme mode ("light" or "dark")

        Returns:
            Hex color string
        """
        theme = "dark" if theme == "dark" else "light"
        key = (status or "unknown").lower()
        return cls._STATUS.get(theme, cls._STATUS["light"]).get(key, "#757575")

    @classmethod
    @lru_cache(maxsize=4)
    def get_colors(cls, theme: str = "light") -> Dict[str, any]:
        """
        Get complete color scheme for theme.

        Args:
            theme: Theme mode ("light" or "dark")

        Returns:
            Dictionary with all theme colors
        """
        theme = "dark" if theme == "dark" else "light"
        if cls._custom:
            return cls._custom.get(theme, cls._custom.get("light", {}))
        base = cls._DEFAULT.get(theme, cls._DEFAULT["light"]).copy()
        base["status"] = cls._STATUS.get(theme, cls._STATUS["light"])
        return base

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached colors."""
        cls.get_status_color.cache_clear()
        cls.get_colors.cache_clear()
