from .hot_models import DeviceStateModel, SyncMetadataModel, DeviceInputModel
from .cold_models import StatusHistoryModel, InputHistoryModel

LatestInput = DeviceInputModel
InputHistory = InputHistoryModel

__all__ = [
    "DeviceStateModel",
    "SyncMetadataModel",
    "DeviceInputModel",
    "StatusHistoryModel",
    "InputHistoryModel",
    "LatestInput",
    "InputHistory",
]
