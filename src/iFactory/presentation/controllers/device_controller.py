"""
Device Controller - Handles device data fetching use case.
Single Responsibility: Load and refresh device list.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from ..ui_state.actions import load_devices

if TYPE_CHECKING:
    from ..presenters.device_presenter import DevicePresenter
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Coordinates device data fetching between Application layer and UI State.
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

    async def refresh_all_devices(self) -> int:
        """
        Fetch devices from Application layer, transform to ViewModels, dispatch to Store.
        Returns count of devices loaded.
        """
        try:
            dtos = await self._device_service.get_all_latest_status()

            if not dtos:
                logger.debug("[DeviceController] No devices returned.")
                return 0

            dto_map = {d.equip_code: d for d in dtos}
            view_models = self._presenter.present_device_list(dto_map)

            self._store.dispatch(load_devices(view_models))
            logger.debug(f"[DeviceController] Loaded {len(view_models)} devices.")
            return len(view_models)

        except Exception as e:
            logger.error(f"[DeviceController] Failed to refresh devices: {e}", exc_info=True)
            return 0

    async def load_from_cache(self) -> int:
        """Load initial state on startup."""
        return await self.refresh_all_devices()


__all__ = ["DeviceController"]
