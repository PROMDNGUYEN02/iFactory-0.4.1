# File: presentation/viewmodels/device_viewmodel.py
"""
Device List ViewModel - With ID Mapping Support.

FIXED:
1. Only discard VERY old results (generation gap > 10)
2. Proper handling of rapid page switching
3. Compatible with current AsyncExecutor
4. NEW: ID mapping support for display vs remote device IDs
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

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

# Only discard if generation is this far behind
GENERATION_DISCARD_THRESHOLD = 10


class IDeviceIdMapper(Protocol):
    """Protocol for device ID mapping (display <-> remote)."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        """Convert display IDs to remote IDs."""
        ...

    def to_display_id(self, remote_id: str) -> str:
        """Convert remote ID to display ID."""
        ...

    def to_remote_id(self, display_id: str) -> str:
        """Convert display ID to remote ID."""
        ...


class NoOpIdMapper:
    """Default mapper that returns IDs unchanged."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        return display_ids

    def to_display_id(self, remote_id: str) -> str:
        return remote_id

    def to_remote_id(self, display_id: str) -> str:
        return display_id


class DeviceListViewModel(BaseViewModel, AsyncViewModelMixin):
    """
    ViewModel for Device List.

    FIXED: Relaxed generation check to handle rapid page switching.
    NEW: ID mapping support for display vs remote device IDs.
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
        id_mapper: Optional[IDeviceIdMapper] = None,  # NEW
        parent=None,
    ):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        self._page_manager = page_manager
        self._remote_source = remote_source
        self._sync_orchestrator = sync_orchestrator
        self._shell_vm = shell_vm
        self._id_mapper = id_mapper or NoOpIdMapper()  # NEW

        self._devices: Dict[str, DeviceDisplayModel] = {}
        self._selected_device_id: Optional[str] = None
        self._sync_status = DeviceSyncStatusModel()

        self._sync_generation: int = 0

        self._executor = AsyncExecutor(max_workers=2, parent=self)

        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

    def initialize(self) -> None:
        logger.info("[DeviceListViewModel] Initializing...")
        self._set_state(UiState.idle())

    def set_shell_viewmodel(self, shell_vm: "ShellViewModel") -> None:
        self._shell_vm = shell_vm
        logger.info("[DeviceListViewModel] ShellViewModel configured")

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        self._remote_source = source

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        self._sync_orchestrator = orchestrator

    def set_id_mapper(self, mapper: IDeviceIdMapper) -> None:
        """Set ID mapper for display <-> remote ID conversion."""
        self._id_mapper = mapper or NoOpIdMapper()

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass
        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)

    def load_devices(self, device_ids: Optional[List[str]] = None) -> None:
        if self._is_disposed:
            return

        codes = device_ids

        if not codes and self._page_manager:
            codes = self._page_manager.get_current_devices()

        if not codes:
            self._set_empty("No devices to load")
            return

        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        codes = [c for c in codes if c not in invalid_keys]

        if not codes:
            self._set_empty("No valid device IDs")
            return

        self._sync_generation += 1
        generation = self._sync_generation

        self._set_loading(True, f"Loading {len(codes)} devices...")
        self._update_sync_status(is_syncing=True)

        logger.info(f"[DeviceListViewModel] Loading {len(codes)} devices (gen={generation})")

        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes, generation)
        elif self._remote_source:
            self._sync_via_remote(codes, generation)
        else:
            self._set_error("No data source configured")

    def refresh(self) -> None:
        if self._is_disposed:
            return
        self.load_devices()

    def select_device(self, device_id: str, open_panel: bool = False) -> None:
        if self._is_disposed:
            return

        logger.debug(f"[DeviceListViewModel] select_device: {device_id}, open_panel={open_panel}")

        is_same_device = self._selected_device_id == device_id
        self._selected_device_id = device_id

        selection = DeviceSelectionModel(
            selected_device_id=device_id,
            is_panel_open=self._shell_vm.right_panel_expanded if self._shell_vm else False,
        )

        self.selectionChanged.emit(selection)

        if open_panel and self._shell_vm:
            if is_same_device:
                self._shell_vm.toggle_right_panel()
            else:
                if not self._shell_vm.right_panel_expanded:
                    self._shell_vm.open_right_panel()

    def deselect_device(self) -> None:
        if self._is_disposed:
            return

        self._selected_device_id = None
        self.selectionChanged.emit(DeviceSelectionModel())
        logger.info("[DeviceListViewModel] Device deselected")

        if self._shell_vm and self._shell_vm.right_panel_expanded:
            self._shell_vm.close_right_panel()

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

    def _sync_via_orchestrator(self, device_ids: List[str], generation: int) -> None:
        """
        Sync via orchestrator.

        Note: The orchestrator already has id_mapper injected,
        so it handles the display->remote->display conversion internally.
        """
        self._executor.execute(
            self._do_orchestrator_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_orchestrator_sync(self, device_ids: List[str], generation: int) -> Dict[str, Any]:
        if not self._sync_orchestrator:
            return {"devices": {}, "count": 0, "error": "No orchestrator", "generation": generation}

        try:
            # Orchestrator handles ID mapping internally
            result = await self._sync_orchestrator.sync_latest_status(device_ids)

            if not result.success:
                return {"devices": {}, "count": 0, "error": result.error, "generation": generation}

            display_models = {}
            for code, device_data in result.devices.items():
                model = self._transform_to_display_model(code, device_data)
                display_models[code] = model

            return {
                "devices": display_models,
                "count": result.count,
                "timestamp": result.timestamp,
                "generation": generation,
            }

        except Exception as e:
            logger.error(f"[DeviceListViewModel] Orchestrator sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e), "generation": generation}

    def _sync_via_remote(self, device_ids: List[str], generation: int) -> None:
        """
        Direct sync via remote source (fallback when no orchestrator).

        NEW: Apply ID mapping here since we're bypassing the orchestrator.
        """
        self._executor.execute(
            self._do_remote_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_remote_sync(self, device_ids: List[str], generation: int) -> Dict[str, Any]:
        if not self._remote_source:
            return {"devices": {}, "count": 0, "error": "No remote source", "generation": generation}

        try:
            # NEW: Convert display IDs to remote IDs for fetching
            remote_ids = self._id_mapper.to_remote_ids(device_ids)

            logger.debug(f"[DeviceListViewModel] Fetching remote IDs: {remote_ids}")

            records = await self._remote_source.fetch_latest_status(remote_ids)

            if not records:
                return {"devices": {}, "count": 0, "generation": generation}

            display_models = {}
            for record in records:
                # NEW: Convert remote code back to display code
                remote_code = record.get("equip_code", "")
                if remote_code:
                    display_code = self._id_mapper.to_display_id(remote_code)
                    model = self._transform_record_to_display_model(record, display_code)
                    display_models[display_code] = model

            return {"devices": display_models, "count": len(display_models), "generation": generation}

        except Exception as e:
            logger.error(f"[DeviceListViewModel] Remote sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e), "generation": generation}

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        if self._is_disposed:
            return

        result_generation = result.get("generation", 0)
        current_generation = self._sync_generation

        # FIXED: Only discard if VERY far behind
        generation_gap = current_generation - result_generation
        if generation_gap > GENERATION_DISCARD_THRESHOLD:
            logger.debug(
                f"[DeviceListViewModel] Discarding very old sync " f"(gen={result_generation}, current={current_generation}, gap={generation_gap})"
            )
            return

        devices = result.get("devices", {})
        count = result.get("count", 0)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if count == 0:
            error_msg = result.get("error")
            if error_msg:
                logger.warning(f"[DeviceListViewModel] Sync completed with error: {error_msg}")
            self._update_sync_status(is_syncing=False, last_sync_time=timestamp)
            return

        logger.info(f"[DeviceListViewModel] Sync success: {count} devices")

        # Merge new devices with existing
        self._devices.update(devices)

        self._update_sync_status(
            is_syncing=False,
            last_sync_time=timestamp,
            synced_count=count,
        )

        # Emit ALL devices
        self.devicesChanged.emit(self._get_devices_as_dict())
        self._set_success(data=self._devices, message=f"Synced {count} devices")

    def _on_sync_error(self, error: Exception) -> None:
        if self._is_disposed:
            return

        error_msg = str(error)
        logger.error(f"[DeviceListViewModel] Sync error: {error_msg}")

        self._update_sync_status(is_syncing=False, error_message=error_msg)
        self._set_error(f"Sync failed: {error_msg}")

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

    def _transform_record_to_display_model(self, record: Dict, display_code: Optional[str] = None) -> DeviceDisplayModel:
        """
        Transform a database record to a display model.

        Args:
            record: Raw database record
            display_code: Override code to use (for ID mapping).
                         If None, uses record's equip_code.
        """
        # Use display_code if provided, otherwise use record's code
        code = display_code or record.get("equip_code", "UNKNOWN")
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

        # Deselect device when changing pages
        if self._selected_device_id:
            self._selected_device_id = None
            self.selectionChanged.emit(DeviceSelectionModel())

            if self._shell_vm and self._shell_vm.right_panel_expanded:
                self._shell_vm.close_right_panel()

        # Load devices for new page
        self.load_devices(device_codes)

    def dispose(self) -> None:
        if self._is_disposed:
            return

        # Mark as disposed first
        self._is_disposed = True

        # Increment generation to invalidate pending results
        self._sync_generation += 1000

        # Shutdown executor
        if self._executor:
            try:
                self._executor.shutdown(wait=False)
            except Exception as e:
                logger.debug(f"Executor shutdown: {e}")

        # Disconnect page manager
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        # Call parent dispose
        BaseViewModel.dispose(self)
        logger.info("[DeviceListViewModel] Disposed")


__all__ = ["DeviceListViewModel"]
