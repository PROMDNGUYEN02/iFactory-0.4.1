# File: presentation/viewmodels/device_viewmodel.py
"""
Device List ViewModel - Optimized for performance.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Signal, Slot

from .base import AsyncViewModelMixin, BaseViewModel, UiState
from .models.device_model import (
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
)
from ..constants.status import Status, StatusCode
from ..adapters.async_executor import AsyncExecutor

if TYPE_CHECKING:
    from ..services.page_device_manager import PageDeviceManager
    from iFactory.application.ports.remote import IRemoteDataSource
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from .shell_viewmodel import ShellViewModel

logger = logging.getLogger(__name__)


class DeviceListViewModel(BaseViewModel, AsyncViewModelMixin):
    """
    ViewModel for Device List - Optimized.

    Key changes:
    - Simplified selection logic
    - Panel state management delegated to ShellViewModel
    - Removed redundant state tracking
    """

    devicesChanged = Signal(dict)
    selectionChanged = Signal(object)
    syncStatusChanged = Signal(object)

    def __init__(
        self,
        page_manager: Optional["PageDeviceManager"] = None,
        remote_source: Optional["IRemoteDataSource"] = None,
        sync_orchestrator: Optional["SyncOrchestrator"] = None,
        shell_vm: Optional["ShellViewModel"] = None,
        parent=None,
    ):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        self._page_manager = page_manager
        self._remote_source = remote_source
        self._sync_orchestrator = sync_orchestrator
        self._shell_vm = shell_vm

        # Internal state
        self._devices: Dict[str, DeviceDisplayModel] = {}
        self._selected_device_id: Optional[str] = None
        self._sync_status = DeviceSyncStatusModel()

        # Async executor
        self._executor = AsyncExecutor(max_workers=2, parent=self)

        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

    def initialize(self) -> None:
        logger.info("[DeviceListViewModel] Initializing...")
        self._set_state(UiState.idle())

    # =========================================================================
    # Configuration
    # =========================================================================

    def set_shell_viewmodel(self, shell_vm: "ShellViewModel") -> None:
        self._shell_vm = shell_vm
        logger.info("[DeviceListViewModel] ShellViewModel configured")

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        self._remote_source = source

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        self._sync_orchestrator = orchestrator

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass
        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)

    # =========================================================================
    # Public API - User Actions
    # =========================================================================

    def load_devices(self, device_ids: Optional[List[str]] = None) -> None:
        """Load/sync devices."""
        if self._is_disposed:
            return

        if not self._mark_operation_started("sync"):
            logger.debug("[DeviceListViewModel] Sync already in progress")
            return

        codes = device_ids
        if not codes and self._page_manager:
            codes = self._page_manager.get_current_devices()

        if not codes:
            self._mark_operation_completed("sync")
            self._set_empty("No devices to load")
            return

        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        codes = [c for c in codes if c not in invalid_keys]

        if not codes:
            self._mark_operation_completed("sync")
            self._set_empty("No valid device IDs")
            return

        self._set_loading(True, f"Loading {len(codes)} devices...")
        self._update_sync_status(is_syncing=True)

        logger.info(f"[DeviceListViewModel] Loading {len(codes)} devices")

        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes)
        elif self._remote_source:
            self._sync_via_remote(codes)
        else:
            self._mark_operation_completed("sync")
            self._set_error("No data source configured")

    def refresh(self) -> None:
        if self._is_disposed:
            return
        self._mark_operation_completed("sync")
        self.load_devices()

    def select_device(self, device_id: str, open_panel: bool = False) -> None:
        """
        Select a device.

        Args:
            device_id: Device to select
            open_panel: If True, toggle panel state (double-click behavior)
                       If False, just select device (single-click behavior)
        """
        if self._is_disposed:
            return

        logger.info(f"[DeviceListViewModel] select_device: {device_id}, open_panel={open_panel}")

        is_same_device = self._selected_device_id == device_id
        was_selected = self._selected_device_id is not None

        # Always update selection
        self._selected_device_id = device_id

        # Create selection model (panel state managed separately)
        selection = DeviceSelectionModel(
            selected_device_id=device_id,
            is_panel_open=self._shell_vm.right_panel_expanded if self._shell_vm else False,
        )

        # Emit selection change
        self.selectionChanged.emit(selection)
        logger.debug(f"[DeviceListViewModel] Selection emitted: {device_id}")

        # Handle panel state via ShellViewModel
        if open_panel and self._shell_vm:
            if is_same_device:
                # Double-click same device → toggle panel
                self._shell_vm.toggle_right_panel()
                logger.info(f"[DeviceListViewModel] Toggle panel for same device")
            else:
                # Double-click different device → open panel if not already open
                if not self._shell_vm.right_panel_expanded:
                    self._shell_vm.open_right_panel()
                    logger.info(f"[DeviceListViewModel] Open panel for new device")
                # If panel already open, just update content (selection already emitted)

    def deselect_device(self) -> None:
        """Deselect current device and close panel."""
        if self._is_disposed:
            return

        self._selected_device_id = None

        selection = DeviceSelectionModel()
        self.selectionChanged.emit(selection)

        logger.info("[DeviceListViewModel] Device deselected")

        # Close panel
        if self._shell_vm and self._shell_vm.right_panel_expanded:
            self._shell_vm.close_right_panel()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def devices(self) -> Dict[str, DeviceDisplayModel]:
        return self._devices.copy()

    @property
    def selected_device_id(self) -> Optional[str]:
        return self._selected_device_id

    @property
    def selected_device(self) -> Optional[DeviceDisplayModel]:
        if not self._selected_device_id:
            return None
        return self._devices.get(self._selected_device_id)

    @property
    def device_count(self) -> int:
        return len(self._devices)

    @property
    def sync_status(self) -> DeviceSyncStatusModel:
        return self._sync_status

    # =========================================================================
    # Internal - Sync Operations
    # =========================================================================

    def _sync_via_orchestrator(self, device_ids: List[str]) -> None:
        self._executor.execute(
            self._do_orchestrator_sync(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_orchestrator_sync(self, device_ids: List[str]) -> Dict[str, Any]:
        if not self._sync_orchestrator:
            return {"devices": {}, "count": 0, "error": "No orchestrator"}

        try:
            result = await self._sync_orchestrator.sync_latest_status(device_ids)

            if not result.success:
                return {"devices": {}, "count": 0, "error": result.error}

            display_models = {}
            for code, device_data in result.devices.items():
                model = self._transform_to_display_model(code, device_data)
                display_models[code] = model

            return {
                "devices": display_models,
                "count": result.count,
                "timestamp": result.timestamp,
            }

        except Exception as e:
            logger.error(f"[DeviceListViewModel] Orchestrator sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

    def _sync_via_remote(self, device_ids: List[str]) -> None:
        self._executor.execute(
            self._do_remote_sync(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_remote_sync(self, device_ids: List[str]) -> Dict[str, Any]:
        if not self._remote_source:
            return {"devices": {}, "count": 0, "error": "No remote source"}

        try:
            records = await self._remote_source.fetch_latest_status(device_ids)

            if not records:
                return {"devices": {}, "count": 0}

            display_models = {}
            for record in records:
                code = record.get("equip_code", "")
                if code:
                    model = self._transform_record_to_display_model(record)
                    display_models[code] = model

            return {"devices": display_models, "count": len(display_models)}

        except Exception as e:
            logger.error(f"[DeviceListViewModel] Remote sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e)}

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        if self._is_disposed:
            return

        self._mark_operation_completed("sync")

        devices = result.get("devices", {})
        count = result.get("count", 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

        logger.info(f"[DeviceListViewModel] Sync success: {count} devices")

        if count == 0:
            self._update_sync_status(is_syncing=False, last_sync_time=timestamp)
            self._set_empty("No devices found")
            return

        self._devices = devices
        self._update_sync_status(
            is_syncing=False,
            last_sync_time=timestamp,
            synced_count=count,
        )

        self.devicesChanged.emit(self._get_devices_as_dict())
        self._set_success(data=devices, message=f"Synced {count} devices")

    def _on_sync_error(self, error: Exception) -> None:
        if self._is_disposed:
            return

        self._mark_operation_completed("sync")
        error_msg = str(error)
        logger.error(f"[DeviceListViewModel] Sync error: {error_msg}")

        self._update_sync_status(is_syncing=False, error_message=error_msg)
        self._set_error(f"Sync failed: {error_msg}")

    # =========================================================================
    # Internal - Data Transformation
    # =========================================================================

    def _transform_to_display_model(self, code: str, device_data: Any) -> DeviceDisplayModel:
        if hasattr(device_data, "equip_code"):
            status_code = self._parse_status(device_data.status_code)
            name = device_data.equip_name or code
            last_update = device_data.last_update
        elif isinstance(device_data, dict):
            status_code = self._parse_status(device_data.get("status_code", 0))
            name = device_data.get("name") or device_data.get("equip_name") or code
            last_update = device_data.get("last_update")
        else:
            return DeviceDisplayModel.empty(code)

        return DeviceDisplayModel(
            device_id=code,
            display_name=f"{name} ({code})" if name != code else code,
            status_code=status_code,
            status_name=Status.get_name(status_code),
            status_color=Status.get_color(status_code),
            status_emoji=Status.get_emoji(status_code),
            is_running=(status_code == StatusCode.RUNNING),
            requires_attention=(status_code in (StatusCode.STOPPED, StatusCode.ALARM)),
            last_update=last_update.isoformat() if hasattr(last_update, "isoformat") else None,
        )

    def _transform_record_to_display_model(self, record: Dict) -> DeviceDisplayModel:
        code = record.get("equip_code", "UNKNOWN")
        name = record.get("equip_name") or code
        status_code = self._parse_status(record.get("equip_status", 0))
        last_update = record.get("last_update")

        return DeviceDisplayModel(
            device_id=code,
            display_name=f"{name} ({code})" if name != code else code,
            status_code=status_code,
            status_name=Status.get_name(status_code),
            status_color=Status.get_color(status_code),
            status_emoji=Status.get_emoji(status_code),
            is_running=(status_code == StatusCode.RUNNING),
            requires_attention=(status_code in (StatusCode.STOPPED, StatusCode.ALARM)),
            last_update=last_update.isoformat() if hasattr(last_update, "isoformat") else None,
        )

    def _parse_status(self, raw: Any) -> int:
        if raw is None:
            return StatusCode.UNKNOWN
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (ValueError, TypeError):
            return StatusCode.UNKNOWN

    def _update_sync_status(
        self,
        is_syncing: bool = None,
        last_sync_time: str = None,
        synced_count: int = None,
        error_message: str = None,
    ) -> None:
        self._sync_status = DeviceSyncStatusModel(
            is_syncing=is_syncing if is_syncing is not None else self._sync_status.is_syncing,
            last_sync_time=last_sync_time or self._sync_status.last_sync_time,
            synced_count=synced_count if synced_count is not None else self._sync_status.synced_count,
            error_message=error_message,
        )
        self.syncStatusChanged.emit(self._sync_status)

    def _get_devices_as_dict(self) -> Dict[str, dict]:
        return {code: model.to_dict() for code, model in self._devices.items()}

    @Slot(str, list)
    def _on_page_changed(self, page_name: str, device_codes: List[str]) -> None:
        if self._is_disposed:
            return

        logger.info(f"[DeviceListViewModel] Page changed: {page_name}, {len(device_codes)} devices")

        # Deselect and close panel when changing pages
        if self._selected_device_id:
            self._selected_device_id = None
            self.selectionChanged.emit(DeviceSelectionModel())

            if self._shell_vm and self._shell_vm.right_panel_expanded:
                self._shell_vm.close_right_panel()

        self._mark_operation_completed("sync")
        self.load_devices(device_codes)

    def dispose(self) -> None:
        if self._is_disposed:
            return

        self._cancel_all_operations()
        self._executor.shutdown(wait=False)

        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        super().dispose()
        logger.info("[DeviceListViewModel] Disposed")


__all__ = ["DeviceListViewModel"]
