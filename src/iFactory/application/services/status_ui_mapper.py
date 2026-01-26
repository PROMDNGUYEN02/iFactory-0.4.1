"""
Status UI Mapper Service.

Maps Domain MachineStatus to UI-specific data (colors, emojis, display).
This responsibility moved from Domain layer to Application layer.

Business Rules:
    - Each status has theme-dependent colors (light/dark)
    - Each status has display text and emoji
    - Category determines groupings for UI organization
"""

from __future__ import annotations

from typing import ClassVar, Dict

__all__ = ["StatusUIMapper"]


class StatusUIMapper:
    """
    Maps Domain MachineStatus to UI-specific presentation data.

    Trách nhiệm:
        - Map status code → color (light/dark theme)
        - Map status code → display text
        - Map status code → emoji
        - Map status code → category

    UI Concerns:
        - Colors for Qt styling
        - Emojis for quick visual context
        - Display text for labels
    """

    # UI data (keys now match MachineStatus.value)
    _UI_DATA: ClassVar[Dict[str, Dict[str, str]]] = {
        "unknown": {
            "display": "UNKNOWN",
            "emoji": "❓",
            "color_light": "#9E9E9E",
            "color_dark": "#757575",
            "category": "unknown",
        },
        "running": {
            "display": "RUNNING",
            "emoji": "🟢",
            "color_light": "#4CAF50",
            "color_dark": "#66BB6A",
            "category": "running",
        },
        "shutdown": {
            "display": "SHUTDOWN",
            "emoji": "⚪",
            "color_light": "#9E9E9E",
            "color_dark": "#E0E0E0",
            "category": "inactive",
        },
        "stopped": {
            "display": "STOP",
            "emoji": "🔴",
            "color_light": "#F44336",
            "color_dark": "#EF5350",
            "category": "stopped",
        },
        "maintenance": {
            "display": "MAINTENANCE",
            "emoji": "🔵",
            "color_light": "#2196F3",
            "color_dark": "#42A5F5",
            "category": "inactive",
        },
        "alarm": {
            "display": "ALARM",
            "emoji": "🟡",
            "color_light": "#FFEB3B",
            "color_dark": "#FFF176",
            "category": "alarm",
        },
    }

    @classmethod
    def get_ui_info(cls, status_code: str, theme: str = "light") -> Dict[str, str | bool]:
        """
        Get UI information for a status code.

        Args:
            status_code: Database status code (e.g., 'running')
            theme: UI theme ('light' or 'dark')

        Returns:
            Dictionary with 'display', 'emoji', 'color', 'category',
            'is_running', 'requires_attention'
        """
        ui_data = cls._UI_DATA.get(status_code, cls._UI_DATA["unknown"])

        is_running = ui_data["category"] == "running"
        requires_attention = ui_data["category"] in ("alarm", "stopped")

        return {
            "display": ui_data["display"],
            "emoji": ui_data["emoji"],
            "color": ui_data["color_light"] if theme == "light" else ui_data["color_dark"],
            "category": ui_data["category"],
            "is_running": is_running,
            "requires_attention": requires_attention,
        }

    @classmethod
    def get_display_text(cls, status_code: str) -> str:
        """Get display text for a status code."""
        return cls._UI_DATA.get(status_code, cls._UI_DATA["unknown"])["display"]

    @classmethod
    def get_emoji(cls, status_code: str) -> str:
        """Get emoji for a status code."""
        return cls._UI_DATA.get(status_code, cls._UI_DATA["unknown"])["emoji"]

    @classmethod
    def get_color(cls, status_code: str, theme: str = "light") -> str:
        """Get color for a status code and theme."""
        ui_data = cls._UI_DATA.get(status_code, cls._UI_DATA["unknown"])
        return ui_data["color_light"] if theme == "light" else ui_data["color_dark"]

    @classmethod
    def get_category(cls, status_code: str) -> str:
        """Get category for a status code."""
        return cls._UI_DATA.get(status_code, cls._UI_DATA["unknown"])["category"]

    @classmethod
    def get_all_ui_data(cls) -> Dict[str, Dict[str, str]]:
        """Get all UI data (for debugging, theme selection)."""
        return cls._UI_DATA.copy()

    @classmethod
    def is_running(cls, status_code: str) -> bool:
        """Check if status represents running state."""
        return cls.get_category(status_code) == "running"

    @classmethod
    def requires_attention(cls, status_code: str) -> bool:
        """Check if status requires operator attention."""
        category = cls.get_category(status_code)
        return category in ("alarm", "stopped")
