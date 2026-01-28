"""
Device Controller - Handles device data fetching use case.
Single Responsibility: Load and refresh device list with Auto-Polling.
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
    Coordinates device data fetching between Application layer and UI State.
    Includes an internal Timer to poll for data changes.
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

        # --- Setup Auto-Refresh Timer ---
        self._timer = QTimer(self)
        self._timer.setInterval(UIConstants.FAST_REFRESH_MS)
        self._timer.timeout.connect(self._on_timer_tick)

        # Start polling immediately upon creation
        self.start_polling()

    def start_polling(self):
        """Enable auto-refresh."""
        if not self._is_active:
            self._is_active = True
            self._timer.start()
            logger.info(f"[DeviceController] Polling started (Interval: {UIConstants.FAST_REFRESH_MS}ms)")
            # Trigger immediate fetch
            self._on_timer_tick()

    def stop_polling(self):
        """Disable auto-refresh."""
        self._timer.stop()
        self._is_active = False
        logger.info("[DeviceController] Polling stopped")

    def _on_timer_tick(self):
        """Handle timer tick: Schedule async refresh task."""
        # Use asyncio.create_task to run async method from sync Qt slot
        asyncio.create_task(self.refresh_all_devices())

    async def refresh_all_devices(self) -> int:
        """
        Fetch devices from Application layer, transform to ViewModels, dispatch to Store.
        Returns count of devices loaded.
        """
        try:
            # 1. Fetch DTOs (Data)
            dtos = await self._device_service.get_all_latest_status()

            if not dtos:
                pass

            # 2. Transform (Presentation Logic)
            dto_map = {d.equip_code: d for d in dtos}
            view_models = self._presenter.present_device_list(dto_map)

            # 3. Update State (UI)
            self._store.dispatch(load_devices(view_models))

            return len(view_models)

        except Exception as e:
            logger.error(f"[DeviceController] Failed to refresh devices: {e}")
            return 0

    async def load_from_cache(self) -> int:
        """Load initial state on startup."""
        return await self.refresh_all_devices()
