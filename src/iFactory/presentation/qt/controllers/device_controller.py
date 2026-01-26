"""
Device Controller - Coordinates Device Use Cases and Updates UI Store.
"""

from __future__ import annotations
import logging
from PySide6.QtCore import QObject
from ...ui_state.actions import load_devices

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

    async def load_devices(self) -> None:
        """
        1. Fetch data from Application layer.
        2. Presenter transforms to ViewModel.
        3. Dispatch to Store.
        """
        try:
            # Application call
            dtos = await self._device_service.get_all_latest_status()

            # Presentation transformation
            view_models = self._presenter.present_device_list({d.equip_code: d for d in dtos})

            # State dispatch
            self._store.dispatch(load_devices(view_models))
        except Exception as e:
            logger.error(f"Failed to load devices: {e}", exc_info=True)
