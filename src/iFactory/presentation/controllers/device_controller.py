# File: presentation/controllers/device_controller.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QTimer

from ..adapters.async_executor import AsyncExecutor
from ..constants.timing import Timing
from ..state.actions import load_devices, set_loading, update_system_status

if TYPE_CHECKING:
    from ..presenters.device_presenter import DevicePresenter
    from ..state.store import Store

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    def __init__(
        self,
        device_service,
        presenter: "DevicePresenter",
        store: "Store",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store
        self._is_polling = False

        self._executor = AsyncExecutor(max_workers=2, parent=self)
        self._timer = QTimer(self)
        self._timer.setInterval(Timing.DEVICE_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._on_poll)

    def start_polling(self) -> None:
        if self._is_polling:
            return
        self._is_polling = True
        self._timer.start()
        logger.info("Device polling started (interval: %dms)", Timing.DEVICE_POLL_INTERVAL_MS)
        self._on_poll()

    def stop_polling(self) -> None:
        self._timer.stop()
        self._is_polling = False
        logger.info("Device polling stopped")

    def refresh_now(self) -> None:
        self._on_poll()

    def _on_poll(self) -> None:
        self._executor.execute(
            self._fetch_devices(),
            on_success=self._on_fetch_success,
            on_error=self._on_fetch_error,
        )

    async def _fetch_devices(self) -> int:
        self._store.dispatch(set_loading(True))

        if not self._service:
            return 0

        dtos = await self._service.get_all_latest_status()
        if dtos is None:
            return 0

        dto_map = {d.equip_code: d for d in dtos}
        view_models = self._presenter.present_many(dto_map)
        self._store.dispatch(load_devices(view_models))
        return len(view_models)

    def _on_fetch_success(self, count: int) -> None:
        self._store.dispatch(update_system_status(mssql=True, sqlite=True, message=f"Synced {count} devices"))

    def _on_fetch_error(self, error: Exception) -> None:
        logger.error("Device fetch failed: %s", error)
        self._store.dispatch(update_system_status(mssql=False, sqlite=True, message=f"Error: {error}"))

    def shutdown(self) -> None:
        self.stop_polling()
        self._executor.shutdown(wait=False)
