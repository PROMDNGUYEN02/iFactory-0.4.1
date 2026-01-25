"""
Application Use Cases Package.
Entry point for all business interactors.
"""

# 1. Device Use Cases
from .device.get_all_devices_status import GetAllDevicesStatusUseCase
from .device.get_latest_status import GetLatestDeviceStatusUseCase
from .device.sync_device_status import SyncDeviceStatusUseCase
from .device.get_device_history import GetDeviceHistoryUseCase

# 2. Production Use Cases
from .production.generate_production_timeline import GenerateProductionTimelineUseCase

# TẠM THỜI COMMENT PHẦN ORDER DO CHƯA CODE XONG DOMAIN ENTITY
# 3. Order Use Cases
# from .order.create_order_use_case import CreateOrderUseCase
# from .order.get_order_use_case import GetOrderUseCase
# from .order.approve_order_use_case import ApproveOrderUseCase

__all__ = [
    # Device
    "GetAllDevicesStatusUseCase",
    "GetLatestDeviceStatusUseCase",
    "SyncDeviceStatusUseCase",
    "GetDeviceHistoryUseCase",
    # Production
    "GenerateProductionTimelineUseCase",
    # Order (Tạm thời bỏ comment ra khỏi __all__)
    # "CreateOrderUseCase",
    # "GetOrderUseCase",
    # "ApproveOrderUseCase",
]
