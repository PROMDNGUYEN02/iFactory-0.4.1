# File: presentation/controllers/device_controller.py
"""
Device Controller - Remote-First Architecture with New Sync API.

Fetches status directly from remote, uses SyncOrchestrator with explicit device IDs.
The controller determines which devices to sync based on PageDeviceManager state.
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
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator

logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Controller for device operations.

    Responsibilities:
    - Determine which device IDs to sync (via PageDeviceManager)
    - Pass explicit device IDs to Application Layer (SyncOrchestrator)
    - Convert sync results to UI state updates
    - Handle sync lifecycle (start/complete/error signals)

    This controller bridges the Presentation Layer (UI concepts like pages)
    with the Application Layer (UI-agnostic sync operations).
    """

    # Signals for UI coordination
    sync_started = Signal()
    sync_completed = Signal(int)  # count of synced devices
    sync_error = Signal(str)

    def __init__(
        self,
        device_service,  # Legacy - kept for compatibility
        presenter: "DevicePresenter",
        store: "Store",
        page_manager: Optional["PageDeviceManager"] = None,
        remote_source: Optional["IRemoteDataSource"] = None,
        sync_orchestrator: Optional["SyncOrchestrator"] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store
        self._page_manager = page_manager
        self._remote_source = remote_source
        self._sync_orchestrator = sync_orchestrator

        self._executor = AsyncExecutor(max_workers=2, parent=self)
        self._is_syncing = False
        self._is_shutdown = False

        # Connect to page changes
        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

    # -------------------------------------------------------------------------
    # Configuration Methods
    # -------------------------------------------------------------------------

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        """Set remote data source for direct fetching."""
        self._remote_source = source
        logger.info("[DeviceController] Remote source configured")

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        """Set sync orchestrator for coordinated sync operations."""
        self._sync_orchestrator = orchestrator
        logger.info("[DeviceController] Sync orchestrator configured")

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        """Set page manager for device ID resolution."""
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)
        logger.info("[DeviceController] Page manager configured")

    # -------------------------------------------------------------------------
    # Page Change Handler
    # -------------------------------------------------------------------------

    @Slot(str, list)
    def _on_page_changed(self, page_name: str, device_codes: List[str]) -> None:
        """
        Handle page change - sync devices for new page immediately.

        The PageDeviceManager provides the device IDs for the new page.
        We pass these explicitly to the sync operation.
        """
        if self._is_shutdown:
            return

        logger.info(f"[DeviceController] Page changed to {page_name}, " f"syncing {len(device_codes)} devices")

        # Force new sync for page change (cancel current if any)
        self._is_syncing = False
        self.sync_devices(device_codes)

    # -------------------------------------------------------------------------
    # Sync Operations
    # -------------------------------------------------------------------------

    def sync_devices(self, device_ids: Optional[List[str]] = None) -> None:
        """
        Sync devices with explicit device IDs.

        Args:
            device_ids: Explicit list of device IDs to sync.
                       If None, uses current page devices from PageDeviceManager.
        """
        if self._is_shutdown:
            return

        if self._is_syncing:
            logger.debug("[DeviceController] Sync already in progress, skipping")
            return

        # Resolve device IDs if not provided
        codes = device_ids
        if not codes and self._page_manager:
            codes = self._page_manager.get_current_devices()

        if not codes:
            logger.warning("[DeviceController] No device IDs to sync")
            return

        # Validate codes are actual device IDs
        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        if any(c in invalid_keys for c in codes):
            logger.error("[DeviceController] Invalid device codes detected in list")
            return

        self._is_syncing = True
        self.sync_started.emit()
        self._store.dispatch(set_loading(True))

        codes_preview = codes[:5]
        logger.info(f"[DeviceController] Starting sync for {len(codes)} devices: " f"{codes_preview}{'...' if len(codes) > 5 else ''}")

        # Choose sync method based on available components
        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes)
        else:
            self._sync_via_remote_direct(codes)

    def _sync_via_orchestrator(self, device_ids: List[str]) -> None:
        """Sync using SyncOrchestrator (preferred method)."""
        self._executor.execute(
            self._orchestrator_sync(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _orchestrator_sync(self, device_ids: List[str]) -> Dict[str, Any]:
        """Execute sync via orchestrator with explicit device IDs."""
        if not self._sync_orchestrator:
            return {"devices": {}, "count": 0, "error": "No orchestrator"}

        try:
            # Use the new API - pass explicit device IDs
            result = await self._sync_orchestrator.sync_latest_status(device_ids)

            if not result.success:
                return {"devices": {}, "count": 0, "error": result.error}

            # Convert SyncedDeviceData to DTOs for presenter
            from iFactory.application.common.dtos import DeviceStatusDTO

            dtos = []
            for code, device_data in result.devices.items():
                dto = DeviceStatusDTO(
                    equip_code=device_data.equip_code,
                    status_code=device_data.status_code,
                    status_name=device_data.status_name,
                    last_update=device_data.last_update,
                    is_active=device_data.is_active,
                    name=device_data.equip_name,
                )
                dtos.append(dto)

            # Present to ViewModels
            dto_map = {d.equip_code: d for d in dtos}
            view_models = self._presenter.present_many(dto_map)

            return {
                "devices": view_models,
                "count": result.count,
                "timestamp": result.timestamp,
            }

        except Exception as e:
            logger.error(f"[DeviceController] Orchestrator sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

    def _sync_via_remote_direct(self, device_ids: List[str]) -> None:
        """Fallback: Sync directly via remote source."""
        self._executor.execute(
            self._fetch_from_remote(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _fetch_from_remote(self, device_ids: List[str]) -> Dict[str, Any]:
        """Fetch latest status directly from remote MSSQL."""
        if not self._remote_source:
            logger.warning("[DeviceController] No remote source available")
            return {"devices": {}, "count": 0}

        try:
            records = await self._remote_source.fetch_latest_status(device_ids)

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

    # -------------------------------------------------------------------------
    # Sync Result Handlers
    # -------------------------------------------------------------------------

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        """Handle successful sync - update UI immediately."""
        if self._is_shutdown:
            return

        logger.info("[DeviceController] Sync success callback")

        self._is_syncing = False

        devices = result.get("devices", {})
        count = result.get("count", 0)

        logger.info(f"[DeviceController] Sync completed: {count} devices")

        if count == 0:
            self._store.dispatch(set_loading(False))
            self._store.dispatch(update_system_status(mssql=True, sqlite=True, message="No devices found"))
            self.sync_completed.emit(0)
            return

        # Convert ViewModels to dicts for state
        devices_dict = self._viewmodels_to_state(devices)

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

    def _viewmodels_to_state(self, devices: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ViewModels to state dictionaries."""
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
        return devices_dict

    def _on_sync_error(self, error: Exception) -> None:
        """Handle sync error."""
        if self._is_shutdown:
            return

        logger.error(f"[DeviceController] Sync error: {error}")

        self._is_syncing = False

        self._store.dispatch(set_loading(False))
        self._store.dispatch(update_system_status(mssql=False, sqlite=True, message=f"Error: {error}"))

        self.sync_error.emit(str(error))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def refresh_now(self) -> None:
        """Force refresh current page devices."""
        if self._is_shutdown:
            return

        logger.info("[DeviceController] Refresh requested")

        # Get current page devices and sync
        if self._page_manager:
            device_ids = self._page_manager.get_current_devices()
            self._is_syncing = False  # Allow new sync
            self.sync_devices(device_ids)
        else:
            self.sync_devices()

    def sync_all_devices(self) -> None:
        """Sync all known devices (not just current page)."""
        if self._is_shutdown:
            return

        if self._page_manager:
            all_device_ids = self._page_manager.get_all_devices()
            self._is_syncing = False
            self.sync_devices(all_device_ids)

    def start_polling(self) -> None:
        """Start initial sync."""
        logger.info("[DeviceController] Starting initial sync")
        self.sync_devices()

    def stop_polling(self) -> None:
        """Stop polling (no-op in remote-first architecture)."""
        pass

    def shutdown(self) -> None:
        """Clean shutdown."""
        self._is_shutdown = True
        self._is_syncing = False
        self._executor.shutdown(wait=False)
        logger.info("[DeviceController] Shutdown complete")


__all__ = ["DeviceController"]
