"""
StatusInfo - Unified status information value object.

This is the SINGLE representation of status used across the entire application.
It ensures color, tooltip, and display text are ALWAYS consistent.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

__all__ = ["StatusInfo"]


@dataclass(frozen=True, slots=True)
class StatusInfo:
    """
    Immutable value object containing ALL status display information.

    This ensures that color, label, tooltip are ALWAYS derived from
    the same source and therefore ALWAYS consistent.

    Attributes:
        db_code: Database status code (e.g., "1", "2")
        id: Internal identifier (e.g., "run", "idle")
        label: Display label (e.g., "RUN", "IDLE")
        color: Hex color for light theme
        color_dark: Hex color for dark theme
        emoji: Status emoji
        description: Human-readable description
    """

    db_code: str
    id: str
    label: str
    color: str
    color_dark: str
    emoji: str
    description: str

    def get_color(self, theme: str = "light") -> str:
        """Get color for specified theme."""
        return self.color_dark if theme == "dark" else self.color

    @property
    def display_text(self) -> str:
        """Get uppercase display text."""
        return self.label.upper()

    @property
    def display_with_emoji(self) -> str:
        """Get display text with emoji prefix."""
        return f"{self.emoji} {self.label}"

    def get_tooltip(
        self,
        device_code: str = "",
        device_name: str = "",
        since: Optional[datetime] = None,
    ) -> str:
        """
        Generate consistent tooltip text.

        Args:
            device_code: Device identifier
            device_name: Device display name
            since: When this status started

        Returns:
            Formatted tooltip string
        """
        lines = []
        if device_code:
            if device_name and device_name != device_code:
                lines.append(f"📍 {device_name} ({device_code})")
            else:
                lines.append(f"📍 {device_code}")
        lines.append(f"Status: {self.emoji} {self.label}")
        if self.description:
            lines.append(f"  {self.description}")
        if since:
            duration = datetime.now() - since
            total_seconds = int(duration.total_seconds())
            (hours, remainder) = divmod(total_seconds, 3600)
            (minutes, seconds) = divmod(remainder, 60)
            if hours > 0:
                lines.append(f"Duration: {hours}h {minutes}m")
            elif minutes > 0:
                lines.append(f"Duration: {minutes}m {seconds}s")
            else:
                lines.append(f"Duration: {seconds}s")
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StatusInfo):
            return self.db_code == other.db_code
        if isinstance(other, str):
            return self.db_code == other or self.id == other
        return False

    def __hash__(self) -> int:
        return hash(self.db_code)

    def to_dict(self, theme: str = "light") -> dict:
        """Convert to dictionary."""
        return {
            "db_code": self.db_code,
            "id": self.id,
            "label": self.label,
            "color": self.get_color(theme),
            "emoji": self.emoji,
            "description": self.description,
        }

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return f"StatusInfo({self.id}, code={self.db_code}, color={self.color})"
