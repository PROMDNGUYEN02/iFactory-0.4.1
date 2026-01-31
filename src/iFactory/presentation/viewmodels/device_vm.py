"""
Device ViewModel - Pure Data Transfer Object.
Decouples Domain Entities from UI Widgets.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DeviceViewModel:
    """
    Immutable presentation model for Device UI components.
    Contains pre-formatted data ready for binding.
    """

    # Identity
    device_id: str
    display_name: str

    # Status Indicators
    status_code: str
    status_display: str
    status_color: str
    status_emoji: str
    is_running: bool
    requires_attention: bool
    last_update: Optional[str]

    # Performance Metrics
    input_count: int = 0
    output_count: int = 0
    error_count: int = 0
    oee: float = 0.0
    yield_rate: float = 0.0
    cycle_time: float = 0.0
    last_error: Optional[str] = None

    # Metadata
    description: Optional[str] = None
    material_batch: Optional[str] = None
    feeding_time: Optional[str] = None

    @property
    def id(self) -> str:
        """Alias for device_id compatibility."""
        return self.device_id

    @property
    def formatted_oee(self) -> str:
        """Returns OEE as a formatted percentage string."""
        return f"{self.oee:.1f}%"

    @property
    def formatted_yield(self) -> str:
        """Returns Yield Rate as a formatted percentage string."""
        return f"{self.yield_rate:.1f}%"

    @property
    def formatted_cycle_time(self) -> str:
        """Returns Cycle Time with unit."""
        return f"{self.cycle_time:.2f}s"
