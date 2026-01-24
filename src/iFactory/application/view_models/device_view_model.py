"""
Device View Model - UI-specific device representation.

Optimized for Qt Presentation layer.
Separate from DTOs (API) and Domain entities (business).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..services.status_ui_mapper import StatusUIMapper

__all__ = ["DeviceViewModel"]


@dataclass(frozen=True, slots=True)
class DeviceViewModel:
    """
    UI-specific view model for device display.

    Designed for Qt Presentation layer with:
        - UI-ready data (colors, display text, emojis)
        - Computed properties for quick access
        - No business logic (just display)

    Invariants:
        - All UI data pre-computed
        - Immutable (frozen=True)
    """

    device_id: str
    """Unique device identifier."""

    display_name: str
    """Display name for UI."""

    status_code: str
    """Database status code."""

    status_display: str
    """Human-readable status text (e.g., 'RUNNING')."""

    status_emoji: str
    """Unicode emoji for quick visual context."""

    status_color: str
    """Hex color code for current theme."""

    status_category: str
    """Category: 'running', 'stopped', 'alarm', 'inactive', 'unknown'."""

    is_running: bool
    """Whether device is currently running."""

    requires_attention: bool
    """Whether device requires operator attention."""

    last_update: Optional[str]
    """Formatted last update timestamp."""

    @classmethod
    def from_domain_data(
        cls,
        equipment_code: str,
        status_code: str,
        status_name: str,
        theme: str = "light",
        last_update: Optional[str] = None,
    ) -> "DeviceViewModel":
        """
        Create view model from domain data.

        Args:
            equipment_code: Device identifier
            status_code: Database status code
            status_name: Internal status name
            theme: UI theme ('light' or 'dark')
            last_update: Optional formatted timestamp

        Returns:
            DeviceViewModel ready for UI display
        """
        ui_info = StatusUIMapper.get_ui_info(status_code, theme)

        return cls(
            device_id=equipment_code,
            display_name=equipment_code,
            status_code=status_code,
            status_display=ui_info["display"],
            status_emoji=ui_info["emoji"],
            status_color=ui_info["color"],
            status_category=ui_info["category"],
            is_running=ui_info["is_running"],
            requires_attention=ui_info["requires_attention"],
            last_update=last_update,
        )

    def to_dict(self) -> dict:
        """
        Convert to dictionary for signal/data transfer.

        Note: This is for Qt signal serialization, not API responses.
        """
        return {
            "device_id": self.device_id,
            "display_name": self.display_name,
            "status_code": self.status_code,
            "status_display": self.status_display,
            "status_emoji": self.status_emoji,
            "status_color": self.status_color,
            "status_category": self.status_category,
            "is_running": self.is_running,
            "requires_attention": self.requires_attention,
            "last_update": self.last_update,
        }

    def __str__(self) -> str:
        """String representation for debugging."""
        status_part = f"{self.status_emoji} {self.status_display}"
        return f"{self.device_id} - {status_part}"
