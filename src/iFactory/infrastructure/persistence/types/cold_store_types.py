"""Cold store (history) database row types."""

from datetime import datetime
from typing import TypedDict

__all__ = ["StatusHistoryRow", "InputHistoryRow"]


class StatusHistoryRow(TypedDict, total=False):
    """Status history record from cold store."""

    id: int
    EQUIP_CODE: str
    EQUIP_STATUS: str
    START_TIME: datetime
    END_TIME: datetime
    DURATION: float


class InputHistoryRow(TypedDict, total=False):
    """Input history record from cold store."""

    id: int
    EQUIP_CODE: str
    MATERIAL_BATCH: str
    FEEDING_TIME: datetime
