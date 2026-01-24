"""
Device Use Cases Package.

This package contains Use Cases specifically related to the Device aggregate.
These use cases handle intents such as syncing status, retrieving history,
and fetching the latest state of equipment.
"""

from .get_all_devices_status import GetAllDevicesStatusUseCase
from .get_device_history import GetDeviceHistoryUseCase
from .get_latest_status import GetLatestDeviceStatusUseCase
from .sync_device_status import SyncDeviceStatusUseCase

__all__ = [
    "GetAllDevicesStatusUseCase",
    "GetDeviceHistoryUseCase",
    "GetLatestDeviceStatusUseCase",
    "SyncDeviceStatusUseCase",
]
