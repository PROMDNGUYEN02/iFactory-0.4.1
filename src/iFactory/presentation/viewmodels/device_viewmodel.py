# File: presentation/viewmodels/device_viewmodel.py
"""
Device List ViewModel - Per-Page Fetching + Parallel On-Demand Data + Auto-Refresh Panel.

Features:
- Only fetch devices for current page
- Auto-refresh every 3s for current page
- PARALLEL fetching: Availability + Material Inputs fetched simultaneously
- Progressive UI update: Show data as it arrives
- AUTO-REFRESH RIGHT PANEL: Refresh selected device details every 3s when panel is open
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

from PySide6.QtCore import Signal, Slot, QTimer

from .base import AsyncViewModelMixin, BaseViewModel, UiState
from .models.device_model import (
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
    MaterialInputModel,
)
from ..constants.status import Status, StatusCode
from ..adapters.async_executor import AsyncExecutor

if TYPE_CHECKING:
    from ..services.page_device_manager import PageDeviceManager
    from iFactory.application.ports.remote import IRemoteDataSource
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator, DeviceAvailability
    from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter
    from .shell_viewmodel import ShellViewModel

logger = logging.getLogger(__name__)

GENERATION_DISCARD_THRESHOLD = 10
LOAD_DEBOUNCE_MS = 150
PANEL_REFRESH_INTERVAL_MS = 3000  # 3 seconds


class IDeviceIdMapper(Protocol):
    """Protocol for device ID mapping (display <-> remote)."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]: ...
    def to_display_id(self, remote_id: str) -> str: ...
    def to_remote_id(self, display_id: str) -> str: ...


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
    ViewModel for Device List with Parallel On-Demand Fetching + Auto-Refresh Panel.

    Features:
    - Per-page fetching: Only fetch devices visible on current page
    - Auto-refresh: Every 3s for current page only
    - PARALLEL: Availability + Materials fetched simultaneously on device click
    - Progressive UI: Updates panel as each piece of data arrives
    - AUTO-REFRESH PANEL: When panel is open, refresh selected device every 3s
    """

    devicesChanged = Signal(dict)
    selectionChanged = Signal(object)
    syncStatusChanged = Signal(object)
    availabilityChanged = Signal(str, object)
    materialInputsChanged = Signal(str, list)

    def __init__(
        self,
        page_manager: Optional["PageDeviceManager"] = None,
        remote_source: Optional["IRemoteDataSource"] = None,
        sync_orchestrator: Optional["SyncOrchestrator"] = None,
        shell_vm: Optional["ShellViewModel"] = None,
        id_mapper: Optional[IDeviceIdMapper] = None,
        parent=None,
    ):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        self._page_manager = page_manager
        self._remote_source = remote_source
        self._sync_orchestrator = sync_orchestrator
        self._shell_vm = shell_vm
        self._id_mapper = id_mapper or NoOpIdMapper()

        self._devices: Dict[str, DeviceDisplayModel] = {}
        self._selected_device_id: Optional[str] = None
        self._sync_status = DeviceSyncStatusModel()

        self._current_page_name: str = ""
        self._current_page_devices: List[str] = []

        self._sync_generation: int = 0
        self._detail_generation: int = 0
        self._pending_detail_device: Optional[str] = None

        self._executor = AsyncExecutor(max_workers=4, parent=self)

        if self._page_manager:
            self._page_manager.page_changed.connect(self._on_page_changed)

        # Debounce timer for load_devices
        self._load_debounce_timer: Optional[QTimer] = None
        self._pending_load_ids: Optional[List[str]] = None
        self._is_loading: bool = False

        # =====================================================================
        # NEW: Panel auto-refresh timer
        # =====================================================================
        self._panel_refresh_timer: Optional[QTimer] = None
        self._is_panel_open: bool = False

    def initialize(self) -> None:
        logger.info("[DeviceListViewModel] Initializing...")
        self._set_state(UiState.idle())

        # Setup panel refresh timer
        self._setup_panel_refresh_timer()

    def _setup_panel_refresh_timer(self) -> None:
        """Setup timer for auto-refreshing right panel."""
        self._panel_refresh_timer = QTimer(self)
        self._panel_refresh_timer.setInterval(PANEL_REFRESH_INTERVAL_MS)
        self._panel_refresh_timer.timeout.connect(self._on_panel_refresh_tick)
        logger.debug(f"[DeviceListViewModel] Panel refresh timer setup: {PANEL_REFRESH_INTERVAL_MS}ms")

    def set_shell_viewmodel(self, shell_vm: "ShellViewModel") -> None:
        self._shell_vm = shell_vm

        # Connect to panel state changes
        if self._shell_vm:
            self._shell_vm.rightPanelChanged.connect(self._on_right_panel_state_changed)

        logger.info("[DeviceListViewModel] ShellViewModel configured with panel listener")

    @Slot(bool)
    def _on_right_panel_state_changed(self, is_open: bool) -> None:
        """Handle right panel open/close state change."""
        self._is_panel_open = is_open

        if is_open and self._selected_device_id:
            # Panel opened with a device selected - start refresh timer
            self._start_panel_refresh()
        else:
            # Panel closed - stop refresh timer
            self._stop_panel_refresh()

    def _start_panel_refresh(self) -> None:
        """Start auto-refresh timer for right panel."""
        if self._panel_refresh_timer and not self._panel_refresh_timer.isActive():
            self._panel_refresh_timer.start()
            logger.debug(f"[DeviceListViewModel] Panel refresh started for {self._selected_device_id}")

    def _stop_panel_refresh(self) -> None:
        """Stop auto-refresh timer for right panel."""
        if self._panel_refresh_timer and self._panel_refresh_timer.isActive():
            self._panel_refresh_timer.stop()
            logger.debug("[DeviceListViewModel] Panel refresh stopped")

    @Slot()
    def _on_panel_refresh_tick(self) -> None:
        """Called every 3s when panel is open - refresh selected device details."""
        if self._is_disposed:
            self._stop_panel_refresh()
            return

        if not self._is_panel_open or not self._selected_device_id:
            self._stop_panel_refresh()
            return

        # Refresh the selected device details
        logger.debug(f"[DeviceListViewModel] Panel refresh tick: {self._selected_device_id}")
        self._fetch_device_details_parallel(self._selected_device_id)

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        self._remote_source = source

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        self._sync_orchestrator = orchestrator

    def set_id_mapper(self, mapper: IDeviceIdMapper) -> None:
        self._id_mapper = mapper or NoOpIdMapper()

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass
        self._page_manager = manager
        self._page_manager.page_changed.connect(self._on_page_changed)

    @property
    def current_page_devices(self) -> List[str]:
        return self._current_page_devices.copy()

    @property
    def current_page_name(self) -> str:
        return self._current_page_name

    def load_devices(self, device_ids: Optional[List[str]] = None) -> None:
        if self._is_disposed:
            return

        codes = device_ids if device_ids else self._current_page_devices

        if not codes:
            return

        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        codes = [c for c in codes if c not in invalid_keys]

        if not codes:
            return

        self._pending_load_ids = codes

        if self._load_debounce_timer is None:
            self._load_debounce_timer = QTimer(self)
            self._load_debounce_timer.setSingleShot(True)
            self._load_debounce_timer.timeout.connect(self._execute_pending_load)

        if self._is_loading:
            return

        self._load_debounce_timer.stop()
        self._load_debounce_timer.start(LOAD_DEBOUNCE_MS)

    def _execute_pending_load(self) -> None:
        if self._is_disposed or not self._pending_load_ids:
            return

        if self._is_loading:
            self._load_debounce_timer.start(LOAD_DEBOUNCE_MS)
            return

        codes = self._pending_load_ids
        self._pending_load_ids = None
        self._is_loading = True

        self._sync_generation += 1
        generation = self._sync_generation

        self._set_loading(True, f"Loading {len(codes)} devices...")
        self._update_sync_status(is_syncing=True)

        logger.info(f"[DeviceListViewModel] Loading {len(codes)} devices for {self._current_page_name} (gen={generation})")

        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes, generation)
        elif self._remote_source:
            self._sync_via_remote(codes, generation)
        else:
            self._is_loading = False
            self._set_error("No data source configured")

    def refresh(self) -> None:
        if self._is_disposed:
            return
        self.load_devices()

    def load_page(self, page_name: str, device_ids: List[str]) -> None:
        if self._is_disposed:
            return

        logger.info(f"[DeviceListViewModel] Loading page: {page_name} with {len(device_ids)} devices")

        if self._load_debounce_timer:
            self._load_debounce_timer.stop()
        self._pending_load_ids = None

        # Cancel pending detail fetches and stop panel refresh
        self._detail_generation += 100
        self._pending_detail_device = None
        self._stop_panel_refresh()

        self._current_page_name = page_name
        self._current_page_devices = device_ids.copy()

        if self._selected_device_id:
            self._selected_device_id = None
            self.selectionChanged.emit(DeviceSelectionModel())

            if self._shell_vm and self._shell_vm.right_panel_expanded:
                self._shell_vm.close_right_panel()

        if self._sync_orchestrator:
            self._sync_orchestrator.clear_availability_cache()

        self._devices.clear()

        if device_ids:
            self._pending_load_ids = device_ids
            self._execute_pending_load()

    def select_device(self, device_id: str, open_panel: bool = False) -> None:
        """Select device and fetch details in PARALLEL."""
        if self._is_disposed:
            return

        logger.debug(f"[DeviceListViewModel] select_device: {device_id}, open_panel={open_panel}")

        is_same_device = self._selected_device_id == device_id

        # Cancel pending fetches for previous device
        if not is_same_device and self._pending_detail_device:
            self._detail_generation += 10
            self._pending_detail_device = None

        self._selected_device_id = device_id
        self._pending_detail_device = device_id

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

        # PARALLEL FETCH: Availability + Materials simultaneously
        if not is_same_device:
            self._fetch_device_details_parallel(device_id)

        # Start panel refresh if panel is open
        if self._shell_vm and self._shell_vm.right_panel_expanded:
            self._is_panel_open = True
            self._start_panel_refresh()

    # =========================================================================
    # PARALLEL FETCHING
    # =========================================================================

    def _fetch_device_details_parallel(self, device_id: str) -> None:
        """
        Fetch all device details in PARALLEL.
        Each fetch updates UI immediately when complete.
        """
        self._detail_generation += 1
        generation = self._detail_generation
        remote_id = self._id_mapper.to_remote_id(device_id)

        logger.debug(f"[DeviceListViewModel] Parallel fetch for {device_id} (gen={generation})")

        # Launch parallel fetches
        if self._sync_orchestrator:
            self._executor.execute(
                self._do_fetch_availability(device_id, generation),
                on_success=self._on_availability_success,
                on_error=self._on_detail_error,
            )

        if self._remote_source and hasattr(self._remote_source, "fetch_material_inputs"):
            self._executor.execute(
                self._do_fetch_material_inputs(device_id, remote_id, generation),
                on_success=self._on_material_inputs_success,
                on_error=self._on_detail_error,
            )

    async def _do_fetch_availability(
        self,
        device_id: str,
        generation: int,
    ) -> Dict[str, Any]:
        """Async fetch availability."""
        if generation < self._detail_generation - 5 or self._is_disposed:
            return {"device_id": device_id, "generation": generation, "skipped": True, "type": "availability"}

        if self._pending_detail_device != device_id:
            return {"device_id": device_id, "generation": generation, "skipped": True, "type": "availability"}

        if not self._sync_orchestrator:
            return {"device_id": device_id, "generation": generation, "error": "No orchestrator", "type": "availability"}

        try:
            availability = await self._sync_orchestrator.fetch_device_availability(device_id)

            if availability:
                return {
                    "device_id": device_id,
                    "generation": generation,
                    "type": "availability",
                    "availability": availability.availability,
                    "run_time_seconds": availability.run_time_seconds,
                    "total_time_seconds": availability.total_time_seconds,
                }
            else:
                return {
                    "device_id": device_id,
                    "generation": generation,
                    "type": "availability",
                    "availability": 0.0,
                    "run_time_seconds": 0.0,
                    "total_time_seconds": 0.0,
                }

        except Exception as e:
            return {"device_id": device_id, "generation": generation, "error": str(e), "type": "availability"}

    async def _do_fetch_material_inputs(
        self,
        display_id: str,
        remote_id: str,
        generation: int,
    ) -> Dict[str, Any]:
        """Async fetch material inputs."""
        if generation < self._detail_generation - 5 or self._is_disposed:
            return {"device_id": display_id, "generation": generation, "skipped": True, "type": "materials"}

        if self._pending_detail_device != display_id:
            return {"device_id": display_id, "generation": generation, "skipped": True, "type": "materials"}

        try:
            records = await self._remote_source.fetch_material_inputs(remote_id)

            if generation < self._detail_generation - 5 or self._is_disposed:
                return {"device_id": display_id, "generation": generation, "skipped": True, "type": "materials"}

            materials = []
            lot_no = ""

            for record in records:
                if hasattr(record, "to_dict"):
                    data = record.to_dict()
                else:
                    data = record

                mat = MaterialInputModel.from_dict(data)
                materials.append(mat)

                if not lot_no and mat.lot_no:
                    lot_no = mat.lot_no

            return {
                "device_id": display_id,
                "generation": generation,
                "type": "materials",
                "materials": materials,
                "lot_no": lot_no,
                "count": len(materials),
            }

        except Exception as e:
            if not self._is_disposed:
                logger.debug(f"[DeviceListViewModel] Material fetch error: {e}")
            return {"device_id": display_id, "generation": generation, "error": str(e), "type": "materials"}

    def _on_availability_success(self, result: Dict[str, Any]) -> None:
        """Handle availability fetch - UPDATE UI IMMEDIATELY."""
        if self._is_disposed or result.get("skipped"):
            return

        device_id = result.get("device_id")
        generation = result.get("generation", 0)

        if generation < self._detail_generation - 5:
            return

        if device_id != self._selected_device_id:
            return

        if "error" in result:
            logger.debug(f"[DeviceListViewModel] Availability error: {result['error']}")
            return

        if device_id in self._devices:
            old_model = self._devices[device_id]

            updated_model = DeviceDisplayModel(
                device_id=old_model.device_id,
                display_name=old_model.display_name,
                status_code=old_model.status_code,
                status_name=old_model.status_name,
                status_color=old_model.status_color,
                status_emoji=old_model.status_emoji,
                is_running=old_model.is_running,
                requires_attention=old_model.requires_attention,
                last_update=old_model.last_update,
                input_count=old_model.input_count,
                output_count=old_model.output_count,
                error_count=old_model.error_count,
                oee=old_model.oee,
                yield_rate=old_model.yield_rate,
                cycle_time=old_model.cycle_time,
                description=old_model.description,
                material_batch=old_model.material_batch,
                feeding_time=old_model.feeding_time,
                last_error=old_model.last_error,
                availability=result.get("availability", 0.0),
                run_time_seconds=result.get("run_time_seconds", 0.0),
                total_time_seconds=result.get("total_time_seconds", 0.0),
                material_inputs=old_model.material_inputs,
                current_lot_no=old_model.current_lot_no,
            )

            self._devices[device_id] = updated_model

            logger.info(f"[DeviceListViewModel] ✓ Availability: {device_id} = {result.get('availability', 0):.1f}%")

            self.availabilityChanged.emit(device_id, result)
            self._emit_selection_update()

    def _on_material_inputs_success(self, result: Dict[str, Any]) -> None:
        """Handle material inputs fetch - UPDATE UI IMMEDIATELY."""
        if self._is_disposed or result.get("skipped"):
            return

        device_id = result.get("device_id")
        generation = result.get("generation", 0)

        if generation < self._detail_generation - 5:
            return

        if device_id != self._selected_device_id:
            return

        if "error" in result:
            logger.debug(f"[DeviceListViewModel] Materials error: {result['error']}")
            return

        materials: List[MaterialInputModel] = result.get("materials", [])
        lot_no = result.get("lot_no", "")
        count = result.get("count", 0)

        if device_id in self._devices:
            old_model = self._devices[device_id]
            updated_model = old_model.with_material_inputs(materials, lot_no)
            self._devices[device_id] = updated_model

            logger.info(f"[DeviceListViewModel] ✓ Materials: {device_id} = {count} items, LOT: {lot_no}")

            self.materialInputsChanged.emit(device_id, materials)
            self._emit_selection_update()

    def _on_detail_error(self, error: Exception) -> None:
        """Handle detail fetch error - silent for timeout during shutdown."""
        if self._is_disposed:
            return
        if "timed out" not in str(error).lower():
            logger.debug(f"[DeviceListViewModel] Detail fetch error: {error}")

    def _emit_selection_update(self) -> None:
        """Re-emit selection to trigger UI refresh."""
        if self._selected_device_id:
            selection = DeviceSelectionModel(
                selected_device_id=self._selected_device_id,
                is_panel_open=self._shell_vm.right_panel_expanded if self._shell_vm else False,
            )
            self.selectionChanged.emit(selection)

    def deselect_device(self) -> None:
        if self._is_disposed:
            return

        self._detail_generation += 10
        self._pending_detail_device = None
        self._stop_panel_refresh()

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

    # =========================================================================
    # Sync Methods
    # =========================================================================

    def _sync_via_orchestrator(self, device_ids: List[str], generation: int) -> None:
        self._executor.execute(
            self._do_orchestrator_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_orchestrator_sync(self, device_ids: List[str], generation: int) -> Dict[str, Any]:
        if not self._sync_orchestrator:
            return {"devices": {}, "count": 0, "error": "No orchestrator", "generation": generation}

        if generation < self._sync_generation - 5 or self._is_disposed:
            return {"devices": {}, "count": 0, "skipped": True, "generation": generation}

        try:
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
            if not self._is_disposed:
                logger.error(f"[DeviceListViewModel] Orchestrator sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e), "generation": generation}

    def _sync_via_remote(self, device_ids: List[str], generation: int) -> None:
        self._executor.execute(
            self._do_remote_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_remote_sync(self, device_ids: List[str], generation: int) -> Dict[str, Any]:
        if not self._remote_source:
            return {"devices": {}, "count": 0, "error": "No remote source", "generation": generation}

        if generation < self._sync_generation - 5 or self._is_disposed:
            return {"devices": {}, "count": 0, "skipped": True, "generation": generation}

        try:
            remote_ids = self._id_mapper.to_remote_ids(device_ids)
            records = await self._remote_source.fetch_latest_status(remote_ids)

            if not records:
                return {"devices": {}, "count": 0, "generation": generation}

            display_models = {}
            for record in records:
                remote_code = record.get("equip_code", "")
                if remote_code:
                    display_code = self._id_mapper.to_display_id(remote_code)
                    model = self._transform_record_to_display_model(record, display_code)
                    display_models[display_code] = model

            return {"devices": display_models, "count": len(display_models), "generation": generation}

        except Exception as e:
            if not self._is_disposed:
                logger.error(f"[DeviceListViewModel] Remote sync failed: {e}")
            return {"devices": {}, "count": 0, "error": str(e), "generation": generation}

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        if self._is_disposed or result.get("skipped"):
            self._is_loading = False
            return

        self._is_loading = False

        result_generation = result.get("generation", 0)
        current_generation = self._sync_generation

        generation_gap = current_generation - result_generation
        if generation_gap > GENERATION_DISCARD_THRESHOLD:
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

        logger.info(f"[DeviceListViewModel] Sync success: {count} devices for {self._current_page_name}")

        # Merge: preserve detail data from existing models
        for code, new_model in devices.items():
            if code in self._devices:
                old_model = self._devices[code]
                if old_model.availability > 0 or old_model.run_time_seconds > 0 or old_model.has_material_inputs:
                    devices[code] = DeviceDisplayModel(
                        device_id=new_model.device_id,
                        display_name=new_model.display_name,
                        status_code=new_model.status_code,
                        status_name=new_model.status_name,
                        status_color=new_model.status_color,
                        status_emoji=new_model.status_emoji,
                        is_running=new_model.is_running,
                        requires_attention=new_model.requires_attention,
                        last_update=new_model.last_update,
                        input_count=new_model.input_count,
                        output_count=new_model.output_count,
                        error_count=new_model.error_count,
                        oee=new_model.oee,
                        yield_rate=new_model.yield_rate,
                        cycle_time=new_model.cycle_time,
                        description=new_model.description,
                        material_batch=old_model.material_batch,
                        feeding_time=old_model.feeding_time,
                        last_error=new_model.last_error,
                        availability=old_model.availability,
                        run_time_seconds=old_model.run_time_seconds,
                        total_time_seconds=old_model.total_time_seconds,
                        material_inputs=old_model.material_inputs,
                        current_lot_no=old_model.current_lot_no,
                    )

        self._devices.update(devices)

        self._update_sync_status(
            is_syncing=False,
            last_sync_time=timestamp,
            synced_count=count,
        )

        self.devicesChanged.emit(self._get_devices_as_dict())
        self._set_success(data=self._devices, message=f"Synced {count} devices")

    def _on_sync_error(self, error: Exception) -> None:
        if self._is_disposed:
            return

        self._is_loading = False

        error_msg = str(error)
        logger.error(f"[DeviceListViewModel] Sync error: {error_msg}")

        self._update_sync_status(is_syncing=False, error_message=error_msg)
        self._set_error(f"Sync failed: {error_msg}")

    def _transform_to_display_model(self, code: str, device_data: Any) -> DeviceDisplayModel:
        if hasattr(device_data, "equip_code"):
            status_code = self._parse_status(device_data.status_code)
            name = getattr(device_data, "equip_name", None) or code
            last_update = getattr(device_data, "last_update", None)
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
            last_update=(last_update.isoformat() if hasattr(last_update, "isoformat") else str(last_update) if last_update else None),
            availability=0.0,
            run_time_seconds=0.0,
            total_time_seconds=0.0,
        )

    def _transform_record_to_display_model(
        self,
        record: Dict,
        display_code: Optional[str] = None,
    ) -> DeviceDisplayModel:
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
            availability=0.0,
            run_time_seconds=0.0,
            total_time_seconds=0.0,
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
        self.load_page(page_name, device_codes)

    def dispose(self) -> None:
        if self._is_disposed:
            return

        self._is_disposed = True

        self._sync_generation += 1000
        self._detail_generation += 1000
        self._pending_detail_device = None

        # Stop timers
        self._stop_panel_refresh()
        if self._panel_refresh_timer:
            self._panel_refresh_timer.deleteLater()
            self._panel_refresh_timer = None

        if self._load_debounce_timer:
            self._load_debounce_timer.stop()
            self._load_debounce_timer.deleteLater()
            self._load_debounce_timer = None

        if self._executor:
            try:
                self._executor.shutdown(wait=False)
            except Exception as e:
                logger.debug(f"Executor shutdown: {e}")

        if self._page_manager:
            try:
                self._page_manager.page_changed.disconnect(self._on_page_changed)
            except RuntimeError:
                pass

        # Disconnect shell_vm signals
        if self._shell_vm:
            try:
                self._shell_vm.rightPanelChanged.disconnect(self._on_right_panel_state_changed)
            except RuntimeError:
                pass

        BaseViewModel.dispose(self)
        logger.info("[DeviceListViewModel] Disposed")


__all__ = ["DeviceListViewModel"]
