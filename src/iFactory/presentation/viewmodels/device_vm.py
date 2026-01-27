"""Device ViewModel - Pure read-only data structure for UI binding."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeviceViewModel:
    """Immutable presentation data for a device."""

    device_id: str
    display_name: str
    status_code: str
    status_display: str
    status_color: str
    status_emoji: str
    is_running: bool
    requires_attention: bool
    last_update: Optional[str]

    # Extended metrics (optional)
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    oee: float = 0.0
    yield_rate: float = 0.0
    cycle_time: float = 0.0
    last_error: Optional[str] = None


__all__ = ["DeviceViewModel"]
