from .hot_models import DeviceStateModel, SyncMetadataModel, DeviceInputModel
from .cold_models import StatusHistoryModel, InputHistoryModel

LatestStatus = DeviceStateModel
LatestInput = DeviceInputModel
SyncMeta = SyncMetadataModel
StatusHistory = StatusHistoryModel
InputHistory = InputHistoryModel

__all__ = [
    "DeviceStateModel",
    "SyncMetadataModel",
    "DeviceInputModel",
    "StatusHistoryModel",
    "InputHistoryModel",
    "LatestStatus",
    "LatestInput",
    "SyncMeta",
    "StatusHistory",
    "InputHistory",
]
