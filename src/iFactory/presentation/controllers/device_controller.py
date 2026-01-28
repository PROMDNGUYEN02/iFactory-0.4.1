"""
Device Controller - Handles device data fetching use case.
Single Responsibility: Orchestrate data flow (Service -> Presenter -> Store).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

from ..constants.ui_constants import UIConstants
from ..ui_state.actions import load_devices

if TYPE_CHECKING:
    from ..presenters.device_presenter import DevicePresenter
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Coordinates polling of device status.
    Strictly transport layer: No business logic, no direct UI manipulation.
    """

    def __init__(
        self,
        device_service,
        presenter: "DevicePresenter",
        store: "Store",
        parent=None,
    ):
        super().__init__(parent)
        self._device_service = device_service
        self._presenter = presenter
        self._store = store
        self._is_active = False

        # Internal Polling Mechanism
        self._timer = QTimer(self)
        self._timer.setInterval(UIConstants.FAST_REFRESH_MS)
        self._timer.timeout.connect(self._on_timer_tick)

        self.start_polling()

    def start_polling(self) -> None:
        if not self._is_active:
            self._is_active = True
            self._timer.start()
            logger.info(f"[DeviceController] Polling started ({UIConstants.FAST_REFRESH_MS}ms)")
            self._on_timer_tick()

    def stop_polling(self) -> None:
        self._timer.stop()
        self._is_active = False
        logger.info("[DeviceController] Polling stopped")

    def _on_timer_tick(self) -> None:
        """Bridge Qt Signal to Async Task."""
        asyncio.create_task(self.refresh_all_devices())

    async def refresh_all_devices(self) -> int:
        """
        Execute Use Case: Get Latest Status.
        Flow: Service (DTOs) -> Presenter (VMs) -> Store (Action).
        """
        try:
            # 1. Application Layer Call
            dtos = await self._device_service.get_all_latest_status()
            if not dtos:
                return 0

            # 2. Map DTO List to Dictionary for O(1) Access in Presenter
            dto_map = {d.equip_code: d for d in dtos}

            # 3. Presentation Layer Transformation
            view_models = self._presenter.present_device_list(dto_map)

            # 4. State Dispatch
            self._store.dispatch(load_devices(view_models))

            return len(view_models)

        except Exception as e:
            logger.error(f"[DeviceController] Refresh failed: {e}")
            return 0
