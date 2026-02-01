"""
Device List ViewModel.

This is a TRUE ViewModel that:
- Owns UI state for device list
- Exposes reactive signals for Views to bind
- Orchestrates Use Cases (SyncOrchestrator)
- Transforms DTOs to Display Models
- Coordinates with ShellViewModel for panel state
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
    ViewModel for Device List.

    Responsibilities:
    - Manage device list UI state
    - Handle device sync operations
    - Transform data for display
    - Manage device selection
    - Coordinate with ShellViewModel for panel state

    Signals:
    - devicesChanged: Emitted when device list updates
    - selectionChanged: Emitted when selected device changes
    - syncStatusChanged: Emitted when sync status changes
    """

    # Specific signals for device list
    devicesChanged = Signal(dict)  # Dict[str, DeviceDisplayModel]
    selectionChanged = Signal(object)  # DeviceSelectionModel
    syncStatusChanged = Signal(object)  # DeviceSyncStatusModel

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
        self._selection = DeviceSelectionModel()
        self._sync_status = DeviceSyncStatusModel()

        # Async executor for background operations
        self._executor = AsyncExecutor(max_workers=2, parent=self)

        # Connect to page manager if available
        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

    # =========================================================================
    # Initialization
    # =========================================================================

    def initialize(self) -> None:
        """Initialize ViewModel - load initial device list."""
        logger.info("[DeviceListViewModel] Initializing...")
        self._set_state(UiState.idle())

    # =========================================================================
    # Configuration (Dependency Injection)
    # =========================================================================

    def set_shell_viewmodel(self, shell_vm: "ShellViewModel") -> None:
        """Set shell viewmodel for panel coordination."""
        self._shell_vm = shell_vm
        logger.info("[DeviceListViewModel] ShellViewModel configured")

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        """Set remote data source for fetching."""
        self._remote_source = source
        logger.info("[DeviceListViewModel] Remote source configured")

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        """Set sync orchestrator for coordinated sync."""
        self._sync_orchestrator = orchestrator
        logger.info("[DeviceListViewModel] Sync orchestrator configured")

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        """Set page manager for device ID resolution."""
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)
        logger.info("[DeviceListViewModel] Page manager configured")

    # =========================================================================
    # Public API - User Actions
    # =========================================================================

    def load_devices(self, device_ids: Optional[List[str]] = None) -> None:
        """
        Load/sync devices.

        This is the main entry point for loading devices.
        Views call this method; it orchestrates the sync.

        Args:
            device_ids: Explicit list of device IDs to sync.
                       If None, uses current page devices.
        """
        if self._is_disposed:
            return

        # Prevent duplicate syncs
        if not self._mark_operation_started("sync"):
            logger.debug("[DeviceListViewModel] Sync already in progress")
            return

        # Resolve device IDs
        codes = device_ids
        if not codes and self._page_manager:
            codes = self._page_manager.get_current_devices()

        if not codes:
            self._mark_operation_completed("sync")
            self._set_empty("No devices to load")
            return

        # Validate codes
        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        codes = [c for c in codes if c not in invalid_keys]

        if not codes:
            self._mark_operation_completed("sync")
            self._set_empty("No valid device IDs")
            return

        # Update state to loading
        self._set_loading(True, f"Loading {len(codes)} devices...")
        self._update_sync_status(is_syncing=True)

        logger.info(f"[DeviceListViewModel] Loading {len(codes)} devices")

        # Execute sync
        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes)
        elif self._remote_source:
            self._sync_via_remote(codes)
        else:
            self._mark_operation_completed("sync")
            self._set_error("No data source configured")

    def refresh(self) -> None:
        """Force refresh current page devices."""
        if self._is_disposed:
            return

        self._mark_operation_completed("sync")  # Allow new sync
        self.load_devices()

    def select_device(self, device_id: str, open_panel: bool = False) -> None:
        """
        Select a device.

        Args:
            device_id: Device to select
            open_panel: Whether to open details panel (double-click behavior)
        """
        if self._is_disposed:
            return

        logger.info(f"[DeviceListViewModel] select_device: {device_id}, open_panel={open_panel}")

        # Check if selecting the same device
        is_same_device = self._selection.selected_device_id == device_id

        # Determine panel state
        should_panel_be_open = self._selection.is_panel_open

        if open_panel:
            if is_same_device:
                # Double-click on same device - toggle panel
                should_panel_be_open = not self._selection.is_panel_open
                logger.info(f"[DeviceListViewModel] Toggle panel: {should_panel_be_open}")
            else:
                # Double-click on different device - open panel
                should_panel_be_open = True
                logger.info(f"[DeviceListViewModel] Opening panel for new device")

        # Update selection model
        new_selection = DeviceSelectionModel(
            selected_device_id=device_id,
            is_panel_open=should_panel_be_open,
        )

        # Always emit if device changed or panel state changed
        selection_changed = (
            new_selection.selected_device_id != self._selection.selected_device_id or new_selection.is_panel_open != self._selection.is_panel_open
        )

        if selection_changed:
            self._selection = new_selection
            self.selectionChanged.emit(new_selection)
            logger.debug(f"[DeviceListViewModel] Selection changed: {device_id}, panel: {should_panel_be_open}")

        # Coordinate with ShellViewModel for actual panel visibility
        if self._shell_vm:
            current_panel_expanded = self._shell_vm.right_panel_expanded

            if should_panel_be_open and not current_panel_expanded:
                # Need to open panel
                self._shell_vm.open_right_panel()
                logger.info(f"[DeviceListViewModel] Requested ShellVM to open panel")
            elif not should_panel_be_open and current_panel_expanded:
                # Need to close panel
                self._shell_vm.close_right_panel()
                logger.info(f"[DeviceListViewModel] Requested ShellVM to close panel")
        else:
            logger.warning("[DeviceListViewModel] No ShellViewModel set - cannot control panel")

    def deselect_device(self) -> None:
        """Deselect current device."""
        if self._is_disposed:
            return

        was_panel_open = self._selection.is_panel_open

        self._selection = DeviceSelectionModel()
        self.selectionChanged.emit(self._selection)

        logger.info("[DeviceListViewModel] Device deselected")

        # Close panel if it was open
        if was_panel_open and self._shell_vm:
            self._shell_vm.close_right_panel()
            logger.info("[DeviceListViewModel] Closed panel after deselection")

    def toggle_panel(self) -> None:
        """Toggle details panel for selected device."""
        if not self._selection.has_selection:
            return

        new_panel_state = not self._selection.is_panel_open

        self._selection = DeviceSelectionModel(
            selected_device_id=self._selection.selected_device_id,
            is_panel_open=new_panel_state,
        )
        self.selectionChanged.emit(self._selection)

        # Coordinate with ShellViewModel
        if self._shell_vm:
            if new_panel_state:
                self._shell_vm.open_right_panel()
            else:
                self._shell_vm.close_right_panel()

    # =========================================================================
    # Properties - UI can bind to these
    # =========================================================================

    @property
    def devices(self) -> Dict[str, DeviceDisplayModel]:
        """Get current device list."""
        return self._devices.copy()

    @property
    def selected_device_id(self) -> Optional[str]:
        """Get selected device ID."""
        return self._selection.selected_device_id

    @property
    def selected_device(self) -> Optional[DeviceDisplayModel]:
        """Get selected device model."""
        if not self._selection.has_selection:
            return None
        return self._devices.get(self._selection.selected_device_id)

    @property
    def device_count(self) -> int:
        """Get number of devices."""
        return len(self._devices)

    @property
    def sync_status(self) -> DeviceSyncStatusModel:
        """Get current sync status."""
        return self._sync_status

    # =========================================================================
    # Internal - Sync Operations
    # =========================================================================

    def _sync_via_orchestrator(self, device_ids: List[str]) -> None:
        """Sync using SyncOrchestrator."""
        self._executor.execute(
            self._do_orchestrator_sync(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_orchestrator_sync(self, device_ids: List[str]) -> Dict[str, Any]:
        """Execute orchestrator sync."""
        if not self._sync_orchestrator:
            return {"devices": {}, "count": 0, "error": "No orchestrator"}

        try:
            result = await self._sync_orchestrator.sync_latest_status(device_ids)

            if not result.success:
                return {"devices": {}, "count": 0, "error": result.error}

            # Transform to display models
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
        """Fallback: Sync directly via remote source."""
        self._executor.execute(
            self._do_remote_sync(device_ids),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_remote_sync(self, device_ids: List[str]) -> Dict[str, Any]:
        """Execute remote sync."""
        if not self._remote_source:
            return {"devices": {}, "count": 0, "error": "No remote source"}

        try:
            records = await self._remote_source.fetch_latest_status(device_ids)

            if not records:
                return {"devices": {}, "count": 0}

            # Transform to display models
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

    # =========================================================================
    # Internal - Sync Result Handlers
    # =========================================================================

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        """Handle successful sync."""
        if self._is_disposed:
            return

        self._mark_operation_completed("sync")

        devices = result.get("devices", {})
        count = result.get("count", 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

        logger.info(f"[DeviceListViewModel] Sync success: {count} devices")

        if count == 0:
            self._update_sync_status(
                is_syncing=False,
                last_sync_time=timestamp,
            )
            self._set_empty("No devices found")
            return

        # Update internal state
        self._devices = devices

        # Update sync status
        self._update_sync_status(
            is_syncing=False,
            last_sync_time=timestamp,
            synced_count=count,
        )

        # Emit signals
        self.devicesChanged.emit(self._get_devices_as_dict())
        self._set_success(data=devices, message=f"Synced {count} devices")

    def _on_sync_error(self, error: Exception) -> None:
        """Handle sync error."""
        if self._is_disposed:
            return

        self._mark_operation_completed("sync")

        error_msg = str(error)
        logger.error(f"[DeviceListViewModel] Sync error: {error_msg}")

        self._update_sync_status(
            is_syncing=False,
            error_message=error_msg,
        )

        self._set_error(f"Sync failed: {error_msg}")

    # =========================================================================
    # Internal - Data Transformation
    # =========================================================================

    def _transform_to_display_model(
        self,
        code: str,
        device_data: Any,
    ) -> DeviceDisplayModel:
        """Transform sync result to display model."""
        if hasattr(device_data, "equip_code"):
            # SyncedDeviceData object
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
        """Transform remote record to display model."""
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
        """Parse status code from various formats."""
        if raw is None:
            return StatusCode.UNKNOWN
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (ValueError, TypeError):
            return StatusCode.UNKNOWN

    # =========================================================================
    # Internal - State Updates
    # =========================================================================

    def _update_sync_status(
        self,
        is_syncing: bool = None,
        last_sync_time: str = None,
        synced_count: int = None,
        error_message: str = None,
    ) -> None:
        """Update sync status and emit signal."""
        self._sync_status = DeviceSyncStatusModel(
            is_syncing=is_syncing if is_syncing is not None else self._sync_status.is_syncing,
            last_sync_time=last_sync_time or self._sync_status.last_sync_time,
            synced_count=synced_count if synced_count is not None else self._sync_status.synced_count,
            error_message=error_message,
        )
        self.syncStatusChanged.emit(self._sync_status)

    def _get_devices_as_dict(self) -> Dict[str, dict]:
        """Get devices as plain dictionaries for state storage."""
        return {code: model.to_dict() for code, model in self._devices.items()}

    # =========================================================================
    # Event Handlers
    # =========================================================================

    @Slot(str, list)
    def _on_page_changed(self, page_name: str, device_codes: List[str]) -> None:
        """Handle page change - load new page devices."""
        if self._is_disposed:
            return

        logger.info(f"[DeviceListViewModel] Page changed: {page_name}, {len(device_codes)} devices")

        # Close panel and deselect when changing pages
        if self._selection.has_selection:
            self._selection = DeviceSelectionModel()
            self.selectionChanged.emit(self._selection)

            if self._shell_vm and self._shell_vm.right_panel_expanded:
                self._shell_vm.close_right_panel()

        # Reset and load new page devices
        self._mark_operation_completed("sync")
        self.load_devices(device_codes)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
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
