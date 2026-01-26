"""
Device Controller - Coordinates Device Use Cases and Updates UI Store.
Clean Architecture Compliant: NO direct UI imports, NO direct view mutation.
"""

from __future__ import annotations
import logging
from PySide6.QtCore import QObject
from ..ui_state.actions import load_devices

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Maps hardware sync events and user refreshes to UI State.
    """

    def __init__(self, device_service, presenter, store, parent=None):
        super().__init__(parent)
        self._device_service = device_service
        self._presenter = presenter
        self._store = store
        logger.debug("[DeviceController] Initialized.")

    async def refresh_all_devices(self) -> None:
        """
        1. Fetch data from Application layer.
        2. Presenter transforms to ViewModel.
        3. Dispatch to Store.
        """
        try:
            # Application call (returns DTOs)
            dtos = await self._device_service.get_all_latest_status()

            if not dtos:
                return

            # Map DTOs by equipment code
            dto_map = {d.equip_code: d for d in dtos}

            # Presentation transformation (DTO -> ViewModel)
            view_models = self._presenter.present_device_list(dto_map)

            # State dispatch
            self._store.dispatch(load_devices(view_models))
            logger.debug(f"[DeviceController] Refreshed {len(view_models)} devices.")

        except Exception as e:
            logger.error(f"[DeviceController] Device synchronization failed: {e}", exc_info=True)

    async def load_from_cache(self) -> int:
        """
        Loads the initial state on startup.
        Returns the number of devices loaded.
        """
        await self.refresh_all_devices()
        return len(self._store.get_state().get("devices", {}))


__all__ = ["DeviceController"]
