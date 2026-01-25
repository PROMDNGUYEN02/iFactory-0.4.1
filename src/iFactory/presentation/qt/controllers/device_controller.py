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

    async def refresh_all_devices(self, codes: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            if self._sync_service:
                await self._sync_service.sync_status_hot(codes)

            statuses = await self._device_service.get_all_latest_status(codes)

            # Presentation logic isolated to Presenter
            formatted_data = self._presenter.format_for_update(statuses) if self._presenter else statuses

            # Event dispatching
            if self._signal_adapter:
                self._signal_adapter.emit_device_statuses(formatted_data)

            return formatted_data if formatted_data else {}
        except Exception as e:
            logger.error(f"Device synchronization failed: {e}", exc_info=True)
            # Do not leak exceptions to the UI thread
            return {}

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
