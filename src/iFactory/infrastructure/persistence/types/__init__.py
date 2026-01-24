"""Database row type definitions."""

from .hot_store_types import LatestStatusRow, LatestInputRow
from .cold_store_types import StatusHistoryRow, InputHistoryRow

__all__ = ["LatestStatusRow", "LatestInputRow", "StatusHistoryRow", "InputHistoryRow"]
