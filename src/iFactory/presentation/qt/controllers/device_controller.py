from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional, Dict, Any
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

    async def refresh_all_devices(self, codes: Optional[List[str]] = None) -> dict:
        """FIX: Always return dict to stop 'Refreshing' status in View."""
        try:
            if self._sync_service:
                await self._sync_service.sync_status_hot(codes)

            statuses = await self._device_service.get_all_latest_status(codes)
            formatted = self._presenter.format_for_update(statuses) if self._presenter else statuses

            if self._signal_adapter:
                self._signal_adapter.emit_device_statuses(formatted)

            # Return result instead of None
            return formatted if formatted else {}
        except Exception as e:
            logger.error(f"Refresh task failed: {e}")
            return {}

    async def load_from_cache(self) -> int:
        if not self._device_service:
            return 0
        statuses = await self._device_service.get_all_latest_status()
        if statuses:
            formatted = self._presenter.format_for_update(statuses) if self._presenter else statuses
            if self._signal_adapter:
                self._signal_adapter.emit_device_statuses(formatted)
            return len(statuses)
        return 0
