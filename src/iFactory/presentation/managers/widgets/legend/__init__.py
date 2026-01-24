"""Legend management - UI Infrastructure."""

from .config import LegendConfig
from .status_registry import StatusRegistry, get_status_registry

__all__ = ["LegendConfig", "StatusRegistry", "get_status_registry"]
