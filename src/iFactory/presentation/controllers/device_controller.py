import logging
from typing import List

from PySide6.QtCore import QObject, Slot, Signal, QTimer

from iFactory.application.use_cases.queries.device_queries import DeviceQueries
from iFactory.application.use_cases.commands.sync_commands import SyncDevicesCommand
from iFactory.application.dto.device_dto import DeviceSummaryDTO
from iFactory.presentation.adapters.async_executor import AsyncExecutor
from iFactory.presentation.viewmodels.device_viewmodel import DeviceViewModel

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Controller for Device Management use cases.
    Handles 'Refresh', 'Sync', and 'Select Device' actions.
    """

    devices_loaded = Signal(list)  # List[DeviceViewModel]
    sync_finished = Signal(bool)  # Success/Fail

    def __init__(self, executor: AsyncExecutor, queries: DeviceQueries, sync_command: SyncDevicesCommand, parent=None):
        super().__init__(parent)
        self._executor = executor
        self._queries = queries
        self._sync_command = sync_command

        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self.trigger_sync)

    def start_auto_refresh(self, interval_ms: int = 5000):
        self._auto_refresh_timer.start(interval_ms)

    def stop_auto_refresh(self):
        self._auto_refresh_timer.stop()

    @Slot()
    def load_devices(self):
        """Fetches latest device states for display."""
        self._executor.run(
            self._queries.get_all_summaries(), on_success=self._on_devices_loaded, on_error=lambda err: logger.error(f"Load devices failed: {err}")
        )

    @Slot()
    def trigger_sync(self):
        """Executes the sync command to update system state from external source."""
        self._executor.run(self._sync_command.execute(), on_success=self._on_sync_success, on_error=self._on_sync_error)

    def _on_sync_success(self, _):
        # After sync, reload the view
        self.sync_finished.emit(True)
        self.load_devices()

    def _on_sync_error(self, error: str):
        logger.warning(f"Sync failed: {error}")
        self.sync_finished.emit(False)

    def _on_devices_loaded(self, dtos: List[DeviceSummaryDTO]):
        # Map DTOs to ViewModels
        viewmodels = [DeviceViewModel.from_dto(dto) for dto in dtos]
        self.devices_loaded.emit(viewmodels)
