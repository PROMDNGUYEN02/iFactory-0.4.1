"""
Device Controller - Remote-First Architecture.
Fetches status directly from remote, updates UI immediately.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal, Slot

from ..adapters.async_executor import AsyncExecutor
from ..state.actions import (
    load_devices,
    set_loading,
    update_system_status,
)

if TYPE_CHECKING:
    from ..presenters.device_presenter import DevicePresenter
    from ..state.store import Store
    from ..services.page_device_manager import PageDeviceManager
    from iFactory.application.ports.remote import IRemoteDataSource

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Controller for device operations.
    Remote-First: Fetches directly from MSSQL, no local caching.
    """

    sync_started = Signal()
    sync_completed = Signal(int)
    sync_error = Signal(str)

    def __init__(
        self,
        device_service,
        presenter: "DevicePresenter",
        store: "Store",
        page_manager: Optional["PageDeviceManager"] = None,
        remote_source: Optional["IRemoteDataSource"] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store
        self._page_manager = page_manager
        self._remote_source = remote_source

        self._executor = AsyncExecutor(max_workers=2, parent=self)
        self._is_syncing = False
        self._is_shutdown = False

        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        """Set remote data source for direct fetching."""
        self._remote_source = source
        logger.info("[DeviceController] Remote source configured")

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)

    @Slot(str, list)
    def _on_page_changed(self, page_name: str, device_codes: List[str]) -> None:
        """Handle page change - sync devices for new page immediately."""
        if self._is_shutdown:
            return

        logger.info(f"[DeviceController] Page changed to {page_name}, " f"syncing {len(device_codes)} devices")

        # Force new sync for page change (cancel current if any)
        self._is_syncing = False
        self.sync_devices(device_codes)

    def sync_devices(self, equipment_codes: Optional[List[str]] = None) -> None:
        """Sync devices - fetch directly from remote."""
        if self._is_shutdown:
            return

        if self._is_syncing:
            logger.debug("[DeviceController] Sync already in progress, skipping")
            return

        codes = equipment_codes
        if not codes and self._page_manager:
            codes = self._page_manager.get_current_devices()

        if not codes:
            logger.warning("[DeviceController] No device codes to sync")
            return

        # Validate codes are actual device IDs
        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        if any(c in invalid_keys for c in codes):
            logger.error(f"[DeviceController] Invalid device codes detected")
            return

        self._is_syncing = True
        self.sync_started.emit()
        self._store.dispatch(set_loading(True))

        codes_preview = codes[:5]
        logger.info(f"[DeviceController] Starting remote fetch for {len(codes)} devices: " f"{codes_preview}{'...' if len(codes) > 5 else ''}")

        self._executor.execute(
            self._fetch_from_remote(codes),
            on_success=self._on_fetch_success,
            on_error=self._on_fetch_error,
        )

    async def _fetch_from_remote(
        self,
        equipment_codes: List[str],
    ) -> Dict[str, Any]:
        """Fetch latest status directly from remote MSSQL."""
        if not self._remote_source:
            logger.warning("[DeviceController] No remote source available")
            return {"devices": {}, "count": 0}

        try:
            records = await self._remote_source.fetch_latest_status(equipment_codes)

            if not records:
                logger.warning("[DeviceController] No records returned from remote")
                return {"devices": {}, "count": 0}

            logger.info(f"[DeviceController] Fetched {len(records)} records from remote")

            # Convert to DTOs for presenter
            from iFactory.application.common.dtos import DeviceStatusDTO

            dtos = []
            for record in records:
                dto = DeviceStatusDTO(
                    equip_code=record.get("equip_code", ""),
                    status_code=str(record.get("equip_status", "0")),
                    status_name=self._get_status_name(record.get("equip_status", 0)),
                    last_update=record.get("last_update"),
                    is_active=True,
                    name=record.get("equip_name"),
                )
                dtos.append(dto)

            # Present to ViewModels
            dto_map = {d.equip_code: d for d in dtos}
            view_models = self._presenter.present_many(dto_map)

            return {"devices": view_models, "count": len(view_models)}

        except Exception as e:
            logger.error(f"[DeviceController] Remote fetch failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

    def _get_status_name(self, status_code) -> str:
        """Get status name from code."""
        status_map = {
            0: "Unknown",
            1: "Running",
            2: "Shutdown",
            3: "Stopped",
            4: "Maintenance",
            5: "Alarm",
        }
        try:
            return status_map.get(int(status_code), "Unknown")
        except (ValueError, TypeError):
            return "Unknown"

    def _on_fetch_success(self, result: Dict[str, Any]) -> None:
        """Handle successful fetch - update UI immediately."""
        if self._is_shutdown:
            return

        logger.info("[DeviceController] _on_fetch_success called")

        self._is_syncing = False

        devices = result.get("devices", {})
        count = result.get("count", 0)

        logger.info(f"[DeviceController] Fetch success: {count} devices")

        if count == 0:
            self._store.dispatch(set_loading(False))
            self._store.dispatch(update_system_status(mssql=True, sqlite=True, message="No devices found"))
            return

        # Convert ViewModels to dicts for state
        devices_dict = {}
        for code, vm in devices.items():
            try:
                devices_dict[code] = {
                    "device_id": vm.device_id,
                    "display_name": vm.display_name,
                    "status_code": vm.status_code,
                    "status_name": vm.status_name,
                    "status_color": vm.status_color,
                    "status_emoji": vm.status_emoji,
                    "is_running": vm.is_running,
                    "requires_attention": vm.requires_attention,
                    "last_update": vm.last_update,
                    "input_count": vm.input_count,
                    "output_count": vm.output_count,
                    "error_count": vm.error_count,
                    "oee": vm.oee,
                    "yield_rate": vm.yield_rate,
                    "cycle_time": vm.cycle_time,
                    "description": vm.description,
                    "material_batch": vm.material_batch,
                    "feeding_time": vm.feeding_time,
                    "last_error": vm.last_error,
                    "equip_name": vm.display_name,
                }
            except Exception as e:
                logger.error(f"[DeviceController] Failed to convert VM for {code}: {e}")

        # Update store - triggers UI update via devices_updated signal
        logger.info(f"[DeviceController] Dispatching {len(devices_dict)} devices to store")
        self._store.dispatch(load_devices(devices_dict))
        self._store.dispatch(set_loading(False))

        timestamp = datetime.now().strftime("%H:%M:%S")
        self._store.dispatch(
            update_system_status(
                mssql=True,
                sqlite=True,
                message=f"Synced {count} devices @ {timestamp}",
            )
        )

        self.sync_completed.emit(count)

    def _on_fetch_error(self, error: Exception) -> None:
        """Handle fetch error."""
        if self._is_shutdown:
            return

        logger.error(f"[DeviceController] _on_fetch_error called: {error}")

        self._is_syncing = False

        self._store.dispatch(set_loading(False))
        self._store.dispatch(update_system_status(mssql=False, sqlite=True, message=f"Error: {error}"))

        self.sync_error.emit(str(error))

    def refresh_now(self) -> None:
        """Force refresh current page devices."""
        if self._is_shutdown:
            return

        logger.info("[DeviceController] refresh_now called")
        if self._page_manager:
            codes = self._page_manager.get_current_devices()
            self._is_syncing = False
            self.sync_devices(codes)
        else:
            self.sync_devices()

    def start_polling(self) -> None:
        logger.info("[DeviceController] Starting initial fetch")
        self.sync_devices()

    def stop_polling(self) -> None:
        pass

    def shutdown(self) -> None:
        self._is_shutdown = True
        self._is_syncing = False
        self._executor.shutdown(wait=False)
        logger.info("[DeviceController] Shutdown complete")


__all__ = ["DeviceController"]
