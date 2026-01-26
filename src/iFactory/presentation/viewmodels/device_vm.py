"""
Pure ViewModels for the Presentation Layer.
No business logic. Read-only structures for UI binding.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeviceViewModel:
    """Read-only presentation data for a device."""

    device_id: str
    display_name: str
    status_code: str
    status_display: str
    status_color: str
    status_emoji: str
    is_running: bool
    requires_attention: bool
    last_update: Optional[str]
