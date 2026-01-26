from __future__ import annotations
import logging
from typing import Optional, List, Dict, Any
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    status_updated = Signal(dict)

    def __init__(self, device_service=None, signal_adapter=None, async_executor=None, sync_service=None, device_presenter=None, parent=None):
        super().__init__(parent)
        self._device_service = device_service
        self._signal_adapter = signal_adapter
        self._async_executor = async_executor
        self._sync_service = sync_service
        self._presenter = device_presenter
        self._view = None
        self._logger = logging.getLogger(__name__)

    async def refresh_all_devices(self, codes: list[str] = None):
        try:
            statuses = await self._device_service.get_all_latest_status(codes)
            formatted_data = self._presenter.format_for_update(statuses)

            if self._view:
                self._view.update_devices(formatted_data)

        except Exception as e:
            self._logger.error(f"Device synchronization failed: {e}", exc_info=True)

    async def load_from_cache(self) -> int:
        if not self._device_service:
            return 0

        try:
            statuses = await self._device_service.get_all_latest_status()
            if not statuses:
                return 0

            formatted_data = self._presenter.format_for_update(statuses) if self._presenter else statuses

            if self._signal_adapter:
                self._signal_adapter.emit_device_statuses(formatted_data)

            return len(statuses)
        except Exception as e:
            logger.error(f"Cache loading failed: {e}", exc_info=True)
            return 0
