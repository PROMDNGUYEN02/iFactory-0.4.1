"""
Database ORM models.

Hot Store Models (frequently updated):
    - LatestStatus: Current device status
    - LatestInput: Current material input
    - SyncMeta: Synchronization metadata

Cold Store Models (historical):
    - StatusHistory: Status change history
    - InputHistory: Material input history
"""

from .models_hot import LatestStatus, LatestInput, SyncMeta
from .models_cold import StatusHistory, InputHistory

__all__ = ["LatestStatus", "LatestInput", "SyncMeta", "StatusHistory", "InputHistory"]
