"""Hot store (latest state) database row types."""

from datetime import datetime
from typing import TypedDict

__all__ = ["LatestStatusRow", "LatestInputRow"]


class LatestStatusRow(TypedDict, total=False):
    """Latest device status from hot store."""

    EQUIP_CODE: str
    EQUIP_STATUS: str
    LAST_UPDATE: datetime
    CREATE_DATE: datetime
    START_TIME: datetime
    END_TIME: datetime


class LatestInputRow(TypedDict, total=False):
    """Latest material input from hot store."""

    EQUIP_CODE: str
    MATERIAL_BATCH: str
    FEEDING_TIME: datetime
    CREATE_DATE: datetime
