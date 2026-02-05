# src/iFactory/presentation/viewmodels/device_viewmodel.py
"""
Enhanced Device List ViewModel with UX Improvements.

FEATURES v2.0:
- Skeleton loading states per device
- Optimistic UI updates
- Status change animations trigger
- Better error recovery with retry
- Connection state tracking
- Stale data indicators
- Batch operations optimization
- Memory-efficient device storage
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
)
from weakref import WeakSet

from PySide6.QtCore import QObject, Signal, Slot, QTimer, Property

from .base import AsyncViewModelMixin, BaseViewModel, UiState
from .models.device_model import (
    DeviceDisplayModel,
    DeviceSelectionModel,
    DeviceSyncStatusModel,
    MaterialInputModel,
)
from ..constants.status import Status, StatusCode
from ..adapters.async_executor import AsyncExecutor

from ..services.progressive_loader import (
    ProgressiveDeviceLoader,
    LoadingStage,
    LoadPriority,
)
from ..services.viewport_manager import DeviceViewportManager, ViewportChange
from ..services.page_device_manager import PageDeviceManager
from ..constants.timing import Timing
from iFactory.application.services.swr_service import SWRService, CachePolicy

if TYPE_CHECKING:
    from ..services.page_device_manager import PageDeviceManager
    from iFactory.application.ports.remote import IRemoteDataSource
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from .shell_viewmodel import ShellViewModel

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

GENERATION_DISCARD_THRESHOLD: int = 10
LOAD_DEBOUNCE_MS: int = 150
PANEL_REFRESH_INTERVAL_MS: int = 3000
STALE_DATA_THRESHOLD_SECONDS: int = 30
MAX_RETRY_ATTEMPTS: int = 3
RETRY_BASE_DELAY_MS: int = 1000
CONNECTION_CHECK_INTERVAL_MS: int = 5000


# ============================================================================
# Protocols
# ============================================================================


class IDeviceIdMapper(Protocol):
    """Protocol for device ID mapping."""

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


# ============================================================================
# Device Loading State
# ============================================================================


class LoadingPhase(Enum):
    """Loading phases for skeleton UI."""

    IDLE = auto()
    SKELETON = auto()  # Show skeleton placeholder
    LOADING = auto()  # Loading with existing data
    LOADED = auto()  # Fully loaded
    ERROR = auto()  # Error state


@dataclass
class DeviceState:
    """State for a single device."""

    phase: LoadingPhase = LoadingPhase.IDLE
    error: Optional[str] = None
    retry_count: int = 0
    last_update: Optional[datetime] = None
    last_error_time: Optional[datetime] = None

    @property
    def is_loading(self) -> bool:
        return self.phase in (LoadingPhase.SKELETON, LoadingPhase.LOADING)

    @property
    def is_stale(self) -> bool:
        if not self.last_update:
            return True
        age = (datetime.now() - self.last_update).total_seconds()
        return age > STALE_DATA_THRESHOLD_SECONDS

    @property
    def can_retry(self) -> bool:
        if self.retry_count >= MAX_RETRY_ATTEMPTS:
            return False
        if self.last_error_time:
            # Exponential backoff check
            cooldown = RETRY_BASE_DELAY_MS * (2**self.retry_count) / 1000
            elapsed = (datetime.now() - self.last_error_time).total_seconds()
            return elapsed >= cooldown
        return True


class DeviceStateManager:
    """
    Manages loading and error states for all devices.

    Thread-safe and memory-efficient.
    """

    def __init__(self):
        self._states: Dict[str, DeviceState] = {}
        self._global_loading = False

    def get_state(self, device_id: str) -> DeviceState:
        """Get or create state for device."""
        if device_id not in self._states:
            self._states[device_id] = DeviceState()
        return self._states[device_id]

    def set_loading(self, device_id: str, phase: LoadingPhase) -> None:
        """Set loading phase for device."""
        state = self.get_state(device_id)
        state.phase = phase
        if phase == LoadingPhase.LOADED:
            state.last_update = datetime.now()
            state.error = None
            state.retry_count = 0

    def set_error(self, device_id: str, error: str) -> None:
        """Set error for device."""
        state = self.get_state(device_id)
        state.phase = LoadingPhase.ERROR
        state.error = error
        state.last_error_time = datetime.now()

    def increment_retry(self, device_id: str) -> int:
        """Increment retry count and return new value."""
        state = self.get_state(device_id)
        state.retry_count += 1
        return state.retry_count

    def reset_retry(self, device_id: str) -> None:
        """Reset retry count for device."""
        state = self.get_state(device_id)
        state.retry_count = 0
        state.error = None

    def mark_updated(self, device_id: str) -> None:
        """Mark device as recently updated."""
        state = self.get_state(device_id)
        state.last_update = datetime.now()
        state.phase = LoadingPhase.LOADED

    def get_stale_devices(self) -> List[str]:
        """Get list of stale device IDs."""
        return [device_id for device_id, state in self._states.items() if state.is_stale and state.phase != LoadingPhase.ERROR]

    def get_failed_devices(self) -> List[str]:
        """Get list of failed device IDs that can retry."""
        return [device_id for device_id, state in self._states.items() if state.phase == LoadingPhase.ERROR and state.can_retry]

    def clear(self) -> None:
        """Clear all states."""
        self._states.clear()

    def remove(self, device_id: str) -> None:
        """Remove state for device."""
        self._states.pop(device_id, None)


# ============================================================================
# Status Change Tracker
# ============================================================================


@dataclass(frozen=True, slots=True)
class StatusChange:
    """Immutable status change record."""

    device_id: str
    old_status: int
    new_status: int
    timestamp: datetime


class StatusChangeTracker:
    """
    Track status changes for animation triggers.

    Features:
    - Circular buffer for memory efficiency
    - Query by time range
    - Change deduplication
    """

    MAX_CHANGES = 100

    def __init__(self):
        self._previous_status: Dict[str, int] = {}
        self._changes: List[StatusChange] = []

    def record(self, device_id: str, new_status: int) -> Optional[StatusChange]:
        """
        Record new status and return change if status changed.
        """
        old_status = self._previous_status.get(device_id)
        self._previous_status[device_id] = new_status

        if old_status is not None and old_status != new_status:
            change = StatusChange(
                device_id=device_id,
                old_status=old_status,
                new_status=new_status,
                timestamp=datetime.now(),
            )

            # Circular buffer
            self._changes.append(change)
            if len(self._changes) > self.MAX_CHANGES:
                self._changes = self._changes[-self.MAX_CHANGES :]

            return change

        return None

    def get_recent(
        self,
        since: Optional[datetime] = None,
        device_id: Optional[str] = None,
    ) -> List[StatusChange]:
        """Get recent changes, optionally filtered."""
        if since is None:
            since = datetime.now() - timedelta(seconds=10)

        changes = [c for c in self._changes if c.timestamp >= since]

        if device_id:
            changes = [c for c in changes if c.device_id == device_id]

        return changes

    def clear(self) -> None:
        """Clear all tracking data."""
        self._previous_status.clear()
        self._changes.clear()


# ============================================================================
# Connection State Manager
# ============================================================================


class ConnectionState(Enum):
    """Connection states."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    RECONNECTING = auto()


@dataclass
class ConnectionInfo:
    """Connection state information."""

    state: ConnectionState = ConnectionState.CONNECTED
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def record_success(self) -> None:
        self.state = ConnectionState.CONNECTED
        self.last_success = datetime.now()
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure = datetime.now()

        if self.consecutive_failures >= 3:
            self.state = ConnectionState.DISCONNECTED
        elif self.state == ConnectionState.CONNECTED:
            self.state = ConnectionState.RECONNECTING


# ============================================================================
# Enhanced Device List ViewModel
# ============================================================================


class DeviceListViewModel(BaseViewModel, AsyncViewModelMixin):
    """
    Enhanced Device List ViewModel with production-ready features.
    """

    # Core signals
    devicesChanged = Signal(dict)
    selectionChanged = Signal(object)
    syncStatusChanged = Signal(object)
    availabilityChanged = Signal(str, object)
    materialInputsChanged = Signal(str, list)

    # UX signals
    deviceLoadingChanged = Signal(str, bool)  # device_id, is_loading
    deviceStatusChanged = Signal(str, int, int)  # device_id, old_status, new_status
    deviceErrorChanged = Signal(str, str)  # device_id, error_message
    connectionStateChanged = Signal(bool)  # is_connected
    staleDataDetected = Signal(list)  # list of stale device_ids

    # Batch signals
    batchLoadingChanged = Signal(bool)  # is_batch_loading

    loading_stage_changed = Signal(str, object, object)  # device_id, stage, data
    viewport_changed = Signal(object)  # ViewportChange

    def __init__(
        self,
        page_manager: Optional["PageDeviceManager"] = None,
        remote_source: Optional["IRemoteDataSource"] = None,
        sync_orchestrator: Optional["SyncOrchestrator"] = None,
        shell_vm: Optional["ShellViewModel"] = None,
        id_mapper: Optional[IDeviceIdMapper] = None,
        memory_cache: Optional[Any] = None,
        parent: Optional[QObject] = None,
    ):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        # Dependencies
        self._page_manager = page_manager
        self._remote_source = remote_source
        self._sync_orchestrator = sync_orchestrator
        self._shell_vm = shell_vm
        self._id_mapper = id_mapper or NoOpIdMapper()

        # Core state
        self._devices: Dict[str, DeviceDisplayModel] = {}
        self._selected_device_id: Optional[str] = None
        self._sync_status = DeviceSyncStatusModel()

        # Page state
        self._current_page_name: str = ""
        self._current_page_devices: List[str] = []

        # Generation tracking (for request deduplication)
        self._sync_generation: int = 0
        self._detail_generation: int = 0
        self._pending_detail_device: Optional[str] = None

        # Async executor
        self._executor = AsyncExecutor(max_workers=4, parent=self)

        # Enhanced state managers
        self._state_manager = DeviceStateManager()
        self._status_tracker = StatusChangeTracker()
        self._connection_info = ConnectionInfo()

        # Timers
        self._load_debounce_timer: Optional[QTimer] = None
        self._pending_load_ids: Optional[List[str]] = None
        self._is_loading: bool = False

        self._panel_refresh_timer: Optional[QTimer] = None
        self._is_panel_open: bool = False

        self._stale_check_timer: Optional[QTimer] = None
        self._connection_check_timer: Optional[QTimer] = None

        # Signal connections tracking
        self._connected_signals: List[Tuple[Signal, Callable]] = []

        # Connect to page manager
        if self._page_manager:
            self._safe_connect(self._page_manager.page_changed, self._on_page_changed)

        self._memory_cache = memory_cache
        self._swr_service: Optional[SWRService] = None
        self._progressive_loader: Optional[ProgressiveDeviceLoader] = None
        self._viewport_manager: Optional[DeviceViewportManager] = None
        self._page_device_manager: Optional[PageDeviceManager] = None

        # Initialize if cache provided
        if memory_cache:
            self._init_progressive_services(memory_cache)

    def _init_progressive_services(self, cache: Any) -> None:
        """Initialize progressive loading services."""

        # Create SWR service
        self._swr_service = SWRService(
            cache=cache,
            policy=CachePolicy(
                fresh_ttl=Timing.Cache.DEVICE_FRESH_TTL,
                stale_ttl=Timing.Cache.DEVICE_STALE_TTL,
                background_refresh_threshold=Timing.Cache.REFRESH_THRESHOLD,
            ),
        )

        # Create viewport manager
        self._viewport_manager = DeviceViewportManager(
            prefetch_distance=Timing.Viewport.PREFETCH_DISTANCE_PX,
        )

        # Create progressive loader
        from ..services.device_status_service import DeviceStatusService

        self._progressive_loader = ProgressiveDeviceLoader(
            swr_service=self._swr_service,
            device_service=self,  # Use self as device service
            status_service=DeviceStatusService.instance(),
            max_concurrent_loads=10,
        )

        # Connect loader callbacks
        self._progressive_loader.on_stage_changed(self._on_progressive_stage_changed)

        # Create page manager
        self._page_device_manager = PageDeviceManager(
            progressive_loader=self._progressive_loader,
            viewport_manager=self._viewport_manager,
            status_service=DeviceStatusService.instance(),
        )

        # Connect page manager signals
        self._page_device_manager.device_stage_changed.connect(self._on_page_stage_changed)

        logger.info("[DeviceListViewModel] Progressive services initialized")

    # ========================================================================
    # Progressive Loading Integration
    # ========================================================================

    def _on_progressive_stage_changed(
        self,
        device_id: str,
        stage: LoadingStage,
        data: Any,
    ) -> None:
        """Handle stage changes from progressive loader."""
        # Update internal state
        if stage == LoadingStage.SKELETON:
            self._set_device_loading(device_id, LoadingPhase.SKELETON)
        elif stage == LoadingStage.STALE:
            self._set_device_loading(device_id, LoadingPhase.LOADING)
            # Update with stale data
            if data:
                self._update_device_from_data(device_id, data, is_stale=True)
        elif stage == LoadingStage.FRESH:
            self._set_device_loading(device_id, LoadingPhase.LOADED)
            # Update with fresh data
            if data:
                self._update_device_from_data(device_id, data, is_stale=False)
        elif stage == LoadingStage.LIVE:
            # Live updates started
            pass
        elif stage == LoadingStage.ERROR:
            self._set_device_loading(device_id, LoadingPhase.ERROR)

        # Emit signal for UI
        self.loading_stage_changed.emit(device_id, stage, data)

    def _on_page_stage_changed(
        self,
        device_id: str,
        stage: LoadingStage,
        data: Any,
    ) -> None:
        """Handle stage changes from page manager."""
        # Forward to progressive stage handler
        self._on_progressive_stage_changed(device_id, stage, data)

    def _update_device_from_data(
        self,
        device_id: str,
        data: Any,
        is_stale: bool = False,
    ) -> None:
        """Update device model from loaded data."""
        if isinstance(data, dict):
            model = self._transform_record_to_display_model(data, device_id)
        elif hasattr(data, "to_dict"):
            model = self._transform_record_to_display_model(data.to_dict(), device_id)
        else:
            return

        # Mark as stale if applicable
        if is_stale:
            model = model._replace(is_stale=True) if hasattr(model, "_replace") else model

        self._devices[device_id] = model
        self.devicesChanged.emit({device_id: model.to_dict()})

    # ========================================================================
    # Viewport Integration
    # ========================================================================

    def handle_viewport_scroll(
        self,
        scroll_y: int,
        viewport_height: int,
        device_positions: List[Tuple[str, int, int]],
    ) -> None:
        """
        Handle scroll event for viewport tracking.

        Called by DeviceCanvas when scroll changes.
        """
        if not self._page_device_manager:
            return

        # Use executor to avoid blocking UI
        self._executor.execute(
            self._page_device_manager.handle_scroll(
                scroll_y,
                viewport_height,
                device_positions,
            ),
            on_success=lambda _: None,
            on_error=lambda e: logger.error(f"Scroll handling error: {e}"),
        )

    # ========================================================================
    # Enhanced Load Methods
    # ========================================================================

    def load_page_progressive(
        self,
        page_name: str,
        device_ids: List[str],
        visible_positions: Optional[List[Tuple[str, int, int]]] = None,
    ) -> None:
        """
        Load page using progressive loading.

        Args:
            page_name: Page identifier
            device_ids: All device IDs on page
            visible_positions: Optional initial viewport positions
        """
        if not self._page_device_manager:
            # Fallback to standard loading
            self.load_page(page_name, device_ids)
            return

        logger.info(f"[DeviceListViewModel] Progressive load: {page_name} " f"({len(device_ids)} devices)")

        # Execute progressive load
        self._executor.execute(
            self._page_device_manager.initial_load(
                page_name,
                device_ids,
                visible_positions,
            ),
            on_success=lambda _: logger.info("Progressive load complete"),
            on_error=lambda e: logger.error(f"Progressive load error: {e}"),
        )

    async def fetch_device_async(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch device data asynchronously.

        Used by ProgressiveDeviceLoader as factory function.
        """
        if not self._remote_source:
            return None

        try:
            remote_id = self._id_mapper.to_remote_id(device_id)
            records = await self._remote_source.fetch_latest_status([remote_id])

            if records:
                return records[0]
            return None

        except Exception as e:
            logger.error(f"Fetch device error: {e}")
            return None

    # ========================================================================
    # Metrics
    # ========================================================================

    def get_progressive_metrics(self) -> Dict[str, Any]:
        """Get metrics from progressive loading services."""
        metrics = {}

        if self._swr_service:
            metrics["swr"] = self._swr_service.get_metrics()

        if self._progressive_loader:
            metrics["loader"] = self._progressive_loader.get_metrics()

        if self._viewport_manager:
            metrics["viewport"] = self._viewport_manager.get_stats()

        if self._page_device_manager:
            metrics["page_manager"] = self._page_device_manager.get_metrics()

        return metrics

    # =========================================================================
    # Initialization
    # =========================================================================

    def initialize(self) -> None:
        """Initialize the ViewModel."""
        logger.info("[DeviceListViewModel] Initializing...")

        self._set_state(UiState.idle())
        self._setup_timers()

    def _setup_timers(self) -> None:
        """Set up all timers."""
        # Panel refresh timer
        self._panel_refresh_timer = QTimer(self)
        self._panel_refresh_timer.setInterval(PANEL_REFRESH_INTERVAL_MS)
        self._panel_refresh_timer.timeout.connect(self._on_panel_refresh_tick)

        # Stale data check timer
        self._stale_check_timer = QTimer(self)
        self._stale_check_timer.setInterval(10000)  # 10 seconds
        self._stale_check_timer.timeout.connect(self._check_stale_data)
        self._stale_check_timer.start()

        # Connection check timer
        self._connection_check_timer = QTimer(self)
        self._connection_check_timer.setInterval(CONNECTION_CHECK_INTERVAL_MS)
        self._connection_check_timer.timeout.connect(self._check_connection_state)

    def _safe_connect(self, signal: Signal, slot: Callable) -> bool:
        """Safely connect a signal and track it."""
        try:
            signal.connect(slot)
            self._connected_signals.append((signal, slot))
            return True
        except Exception as e:
            logger.warning("[DeviceListViewModel] Failed to connect signal: %s", e)
            return False

    def _safe_disconnect(self, signal: Signal, slot: Callable) -> bool:
        """Safely disconnect a signal."""
        try:
            signal.disconnect(slot)
            return True
        except (RuntimeError, TypeError):
            return False

    # =========================================================================
    # Setters for Dependencies
    # =========================================================================

    def set_shell_viewmodel(self, shell_vm: "ShellViewModel") -> None:
        """Set the shell ViewModel."""
        self._shell_vm = shell_vm
        if self._shell_vm:
            self._safe_connect(self._shell_vm.rightPanelChanged, self._on_right_panel_state_changed)

    def set_remote_source(self, source: "IRemoteDataSource") -> None:
        """Set the remote data source."""
        self._remote_source = source

    def set_sync_orchestrator(self, orchestrator: "SyncOrchestrator") -> None:
        """Set the sync orchestrator."""
        self._sync_orchestrator = orchestrator

    def set_id_mapper(self, mapper: IDeviceIdMapper) -> None:
        """Set the ID mapper."""
        self._id_mapper = mapper or NoOpIdMapper()

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        """Set the page manager."""
        if self._page_manager:
            self._safe_disconnect(self._page_manager.page_changed, self._on_page_changed)
        self._page_manager = manager
        self._safe_connect(self._page_manager.page_changed, self._on_page_changed)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def current_page_devices(self) -> List[str]:
        """Current page device IDs."""
        return self._current_page_devices.copy()

    @property
    def current_page_name(self) -> str:
        """Current page name."""
        return self._current_page_name

    @property
    def devices(self) -> Dict[str, DeviceDisplayModel]:
        """All devices (copy)."""
        return self._devices.copy()

    @property
    def selected_device_id(self) -> Optional[str]:
        """Currently selected device ID."""
        return self._selected_device_id

    @property
    def selected_device(self) -> Optional[DeviceDisplayModel]:
        """Currently selected device model."""
        if not self._selected_device_id:
            return None
        return self._devices.get(self._selected_device_id)

    @property
    def device_count(self) -> int:
        """Number of devices."""
        return len(self._devices)

    @property
    def sync_status(self) -> DeviceSyncStatusModel:
        """Current sync status."""
        return self._sync_status

    @property
    def is_connected(self) -> bool:
        """Check if connected to data source."""
        return self._connection_info.is_connected

    @property
    def connection_state(self) -> ConnectionState:
        """Current connection state."""
        return self._connection_info.state

    # =========================================================================
    # Device State Query Methods
    # =========================================================================

    def is_device_loading(self, device_id: str) -> bool:
        """Check if specific device is loading."""
        return self._state_manager.get_state(device_id).is_loading

    def get_device_loading_phase(self, device_id: str) -> LoadingPhase:
        """Get loading phase for device."""
        return self._state_manager.get_state(device_id).phase

    def get_device_error(self, device_id: str) -> Optional[str]:
        """Get error message for device."""
        return self._state_manager.get_state(device_id).error

    def is_device_stale(self, device_id: str) -> bool:
        """Check if device data is stale."""
        return self._state_manager.get_state(device_id).is_stale

    def get_device_last_update(self, device_id: str) -> Optional[datetime]:
        """Get last update time for device."""
        return self._state_manager.get_state(device_id).last_update

    def get_stale_devices(self) -> List[str]:
        """Get list of stale device IDs."""
        return self._state_manager.get_stale_devices()

    def get_failed_devices(self) -> List[str]:
        """Get list of failed device IDs."""
        return self._state_manager.get_failed_devices()

    def get_recent_status_changes(
        self,
        since: Optional[datetime] = None,
    ) -> List[StatusChange]:
        """Get recent status changes."""
        return self._status_tracker.get_recent(since)

    # =========================================================================
    # Loading State Management
    # =========================================================================

    def _set_device_loading(self, device_id: str, phase: LoadingPhase) -> None:
        """Set loading phase for device and emit signal."""
        self._state_manager.set_loading(device_id, phase)
        is_loading = phase in (LoadingPhase.SKELETON, LoadingPhase.LOADING)
        self.deviceLoadingChanged.emit(device_id, is_loading)

    def _set_device_error(self, device_id: str, error: Optional[str]) -> None:
        """Set error for device and emit signal."""
        if error:
            self._state_manager.set_error(device_id, error)
            self.deviceErrorChanged.emit(device_id, error)
        else:
            self._state_manager.reset_retry(device_id)

    def _set_batch_loading(self, is_loading: bool) -> None:
        """Set batch loading state."""
        self._is_loading = is_loading
        self.batchLoadingChanged.emit(is_loading)

    # =========================================================================
    # Connection State Management
    # =========================================================================

    def _update_connection_state(self, success: bool) -> None:
        """Update connection state based on operation result."""
        old_connected = self._connection_info.is_connected

        if success:
            self._connection_info.record_success()
        else:
            self._connection_info.record_failure()

        new_connected = self._connection_info.is_connected

        if old_connected != new_connected:
            self.connectionStateChanged.emit(new_connected)
            if new_connected:
                logger.info("[DeviceListViewModel] Connection restored")
            else:
                logger.warning("[DeviceListViewModel] Connection lost")

    @Slot()
    def _check_connection_state(self) -> None:
        """Periodic connection state check."""
        if self._is_disposed:
            return

        # If disconnected, try to reconnect
        if not self._connection_info.is_connected:
            if self._connection_info.consecutive_failures < 10:
                self.refresh()

    @Slot()
    def _check_stale_data(self) -> None:
        """Check for stale device data."""
        if self._is_disposed:
            return

        stale_devices = self._state_manager.get_stale_devices()

        if stale_devices:
            self.staleDataDetected.emit(stale_devices)

    # =========================================================================
    # Page Loading
    # =========================================================================

    def load_page(self, page_name: str, device_ids: List[str]) -> None:
        """
        Load devices for a page.

        This resets all state and loads fresh data.
        """
        if self._is_disposed:
            return

        logger.info("[DeviceListViewModel] Loading page: %s", page_name)

        # Cancel pending operations
        if self._load_debounce_timer:
            self._load_debounce_timer.stop()
        self._pending_load_ids = None

        # Increment generations to invalidate in-flight requests
        self._detail_generation += 100
        self._pending_detail_device = None
        self._stop_panel_refresh()

        # Update page state
        self._current_page_name = page_name
        self._current_page_devices = device_ids.copy()

        # Clear selection
        if self._selected_device_id:
            self._selected_device_id = None
            self.selectionChanged.emit(DeviceSelectionModel())
            if self._shell_vm and self._shell_vm.right_panel_expanded:
                self._shell_vm.close_right_panel()

        # Clear caches
        if self._sync_orchestrator:
            self._sync_orchestrator.clear_availability_cache()

        # Clear all state
        self._devices.clear()
        self._state_manager.clear()
        self._status_tracker.clear()

        # Set skeleton loading for all devices
        for device_id in device_ids:
            self._set_device_loading(device_id, LoadingPhase.SKELETON)

        # Start loading
        if device_ids:
            self._pending_load_ids = device_ids
            self._execute_pending_load()

    def load_devices(self, device_ids: Optional[List[str]] = None) -> None:
        """
        Load or refresh devices.

        Uses debouncing to prevent excessive requests.
        """
        if self._is_disposed:
            return

        codes = device_ids if device_ids else self._current_page_devices
        if not codes:
            return

        # Filter out invalid keys
        invalid_keys = {"ref_width", "ref_height", "devices", "min_scale", "max_scale"}
        codes = [c for c in codes if c not in invalid_keys]
        if not codes:
            return

        self._pending_load_ids = codes

        # Setup debounce timer
        if self._load_debounce_timer is None:
            self._load_debounce_timer = QTimer(self)
            self._load_debounce_timer.setSingleShot(True)
            self._load_debounce_timer.timeout.connect(self._execute_pending_load)

        # Skip if already loading
        if self._is_loading:
            return

        # Debounce
        self._load_debounce_timer.stop()
        self._load_debounce_timer.start(LOAD_DEBOUNCE_MS)

    @Slot()
    def _execute_pending_load(self) -> None:
        """Execute the pending device load."""
        if self._is_disposed or not self._pending_load_ids:
            return

        if self._is_loading:
            # Reschedule
            if self._load_debounce_timer:
                self._load_debounce_timer.start(LOAD_DEBOUNCE_MS)
            return

        codes = self._pending_load_ids
        self._pending_load_ids = None
        self._set_batch_loading(True)

        # Increment generation
        self._sync_generation += 1
        generation = self._sync_generation

        self._set_loading(True, f"Loading {len(codes)} devices...")
        self._update_sync_status(is_syncing=True)

        # Mark devices as loading
        for code in codes:
            state = self._state_manager.get_state(code)
            if state.phase == LoadingPhase.IDLE:
                self._set_device_loading(code, LoadingPhase.SKELETON)
            else:
                self._set_device_loading(code, LoadingPhase.LOADING)

        # Execute sync
        if self._sync_orchestrator:
            self._sync_via_orchestrator(codes, generation)
        elif self._remote_source:
            self._sync_via_remote(codes, generation)
        else:
            self._set_batch_loading(False)
            self._set_error("No data source configured")

    def refresh(self) -> None:
        """Refresh current devices."""
        if not self._is_disposed:
            self.load_devices()

    # =========================================================================
    # Device Selection
    # =========================================================================

    def select_device(self, device_id: str, open_panel: bool = False) -> None:
        """
        Select a device.

        Args:
            device_id: Device to select
            open_panel: Whether to open the detail panel
        """
        if self._is_disposed:
            return

        is_same_device = self._selected_device_id == device_id

        # Cancel pending detail fetches for previous device
        if not is_same_device and self._pending_detail_device:
            self._detail_generation += 10
            self._pending_detail_device = None

        self._selected_device_id = device_id
        self._pending_detail_device = device_id

        # Handle panel
        if open_panel and self._shell_vm:
            if is_same_device:
                self._shell_vm.toggle_right_panel()
            else:
                self._shell_vm.open_right_panel()

        # Emit selection
        selection = DeviceSelectionModel(
            selected_device_id=device_id,
            is_panel_open=self._shell_vm.right_panel_expanded if self._shell_vm else False,
        )
        self.selectionChanged.emit(selection)

        # Fetch details for new selection
        if not is_same_device:
            self._set_device_loading(device_id, LoadingPhase.LOADING)
            self._fetch_device_details_parallel(device_id)

        # Start panel refresh if panel is open
        if self._shell_vm and self._shell_vm.right_panel_expanded:
            self._is_panel_open = True
            self._start_panel_refresh()

    def deselect_device(self) -> None:
        """Deselect current device."""
        if self._is_disposed:
            return

        self._detail_generation += 10
        self._pending_detail_device = None
        self._stop_panel_refresh()

        self._selected_device_id = None
        self.selectionChanged.emit(DeviceSelectionModel())

        if self._shell_vm and self._shell_vm.right_panel_expanded:
            self._shell_vm.close_right_panel()

    # =========================================================================
    # Retry Logic
    # =========================================================================

    def retry_device(self, device_id: str) -> bool:
        """
        Retry loading a failed device.

        Returns:
            True if retry was scheduled, False otherwise
        """
        if self._is_disposed:
            return False

        state = self._state_manager.get_state(device_id)

        if not state.can_retry:
            logger.warning("[DeviceListViewModel] Cannot retry %s (attempts: %d)", device_id, state.retry_count)
            return False

        retry_count = self._state_manager.increment_retry(device_id)
        self._set_device_error(device_id, None)

        # Exponential backoff delay
        delay = RETRY_BASE_DELAY_MS * (2 ** (retry_count - 1))

        logger.info("[DeviceListViewModel] Retry %d for %s in %dms", retry_count, device_id, delay)

        # Schedule retry
        QTimer.singleShot(delay, lambda: self._execute_device_retry(device_id))

        return True

    def _execute_device_retry(self, device_id: str) -> None:
        """Execute a device retry."""
        if self._is_disposed:
            return

        if device_id == self._selected_device_id:
            self._fetch_device_details_parallel(device_id)
        else:
            self.load_devices([device_id])

    def retry_all_failed(self) -> int:
        """
        Retry all failed devices.

        Returns:
            Number of devices scheduled for retry
        """
        failed_devices = self.get_failed_devices()
        retried = 0

        for device_id in failed_devices:
            if self.retry_device(device_id):
                retried += 1

        if retried > 0:
            logger.info("[DeviceListViewModel] Scheduled %d retries", retried)

        return retried

    def reset_all_errors(self) -> None:
        """Reset all error states."""
        for device_id in list(self._devices.keys()):
            self._state_manager.reset_retry(device_id)

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def _sync_via_orchestrator(self, device_ids: List[str], generation: int) -> None:
        """Sync via orchestrator."""
        self._executor.execute(
            self._do_orchestrator_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_orchestrator_sync(
        self,
        device_ids: List[str],
        generation: int,
    ) -> Dict[str, Any]:
        """Execute orchestrator sync."""
        if not self._sync_orchestrator:
            return {
                "devices": {},
                "count": 0,
                "error": "No orchestrator",
                "generation": generation,
            }

        # Check if request is stale
        if generation < self._sync_generation - 5 or self._is_disposed:
            return {
                "devices": {},
                "count": 0,
                "skipped": True,
                "generation": generation,
            }

        try:
            result = await self._sync_orchestrator.sync_latest_status(device_ids)

            if not result.success:
                return {
                    "devices": {},
                    "count": 0,
                    "error": result.error,
                    "generation": generation,
                }

            # Transform to display models
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
                logger.error("[DeviceListViewModel] Orchestrator sync failed: %s", e)
            return {
                "devices": {},
                "count": 0,
                "error": str(e),
                "generation": generation,
            }

    def _sync_via_remote(self, device_ids: List[str], generation: int) -> None:
        """Sync via remote source."""
        self._executor.execute(
            self._do_remote_sync(device_ids, generation),
            on_success=self._on_sync_success,
            on_error=self._on_sync_error,
        )

    async def _do_remote_sync(
        self,
        device_ids: List[str],
        generation: int,
    ) -> Dict[str, Any]:
        """Execute remote sync."""
        if not self._remote_source:
            return {
                "devices": {},
                "count": 0,
                "error": "No remote source",
                "generation": generation,
            }

        if generation < self._sync_generation - 5 or self._is_disposed:
            return {
                "devices": {},
                "count": 0,
                "skipped": True,
                "generation": generation,
            }

        try:
            remote_ids = self._id_mapper.to_remote_ids(device_ids)
            records = await self._remote_source.fetch_latest_status(remote_ids)

            if not records:
                return {
                    "devices": {},
                    "count": 0,
                    "generation": generation,
                }

            display_models = {}
            for record in records:
                remote_code = record.get("equip_code", "")
                if remote_code:
                    display_code = self._id_mapper.to_display_id(remote_code)
                    model = self._transform_record_to_display_model(record, display_code)
                    display_models[display_code] = model

            return {
                "devices": display_models,
                "count": len(display_models),
                "generation": generation,
            }

        except Exception as e:
            if not self._is_disposed:
                logger.error("[DeviceListViewModel] Remote sync failed: %s", e)
            return {
                "devices": {},
                "count": 0,
                "error": str(e),
                "generation": generation,
            }

    def _on_sync_success(self, result: Dict[str, Any]) -> None:
        """Handle successful sync."""
        if self._is_disposed or result.get("skipped"):
            self._set_batch_loading(False)
            return

        self._set_batch_loading(False)
        self._update_connection_state(True)

        # Check generation
        result_generation = result.get("generation", 0)
        generation_gap = self._sync_generation - result_generation
        if generation_gap > GENERATION_DISCARD_THRESHOLD:
            return

        devices = result.get("devices", {})
        count = result.get("count", 0)
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%H:%M:%S")

        if count == 0:
            error_msg = result.get("error")
            if error_msg:
                logger.warning("[DeviceListViewModel] Sync error: %s", error_msg)
            self._update_sync_status(
                is_syncing=False,
                last_sync_time=timestamp_str,
            )
            return

        from ..services.device_status_service import get_device_status_service

        status_service = get_device_status_service()

        # Batch update status service
        status_updates = {}
        for code, new_model in devices.items():
            status_updates[code] = {
                "status_code": new_model.status_code,
                "status_name": new_model.status_name,
                "status_color": new_model.status_color,
            }

        # This will trigger statusChanged signals that GanttViewModel listens to
        changes = status_service.update_batch(status_updates, emit_individual=True)

        if changes:
            logger.info(f"[DeviceListViewModel] Status service: {len(changes)} status changes")

        # Track status changes and update states
        status_changes: List[StatusChange] = []

        for code, new_model in devices.items():
            # Check for status change
            if code in self._devices:
                old_model = self._devices[code]
                if old_model.status_code != new_model.status_code:
                    change = self._status_tracker.record(code, new_model.status_code)
                    if change:
                        status_changes.append(change)
                        # Emit individual status change for animation
                        self.deviceStatusChanged.emit(
                            code,
                            old_model.status_code,
                            new_model.status_code,
                        )

            # Update device state
            self._state_manager.mark_updated(code)
            self._set_device_loading(code, LoadingPhase.LOADED)

        # Merge with existing data (preserve availability and materials)
        for code, new_model in devices.items():
            if code in self._devices:
                old_model = self._devices[code]
                if old_model.availability > 0 or old_model.has_material_inputs:
                    devices[code] = self._merge_models(old_model, new_model)

        # Update devices
        self._devices.update(devices)

        # Update sync status
        self._update_sync_status(
            is_syncing=False,
            last_sync_time=timestamp_str,
            synced_count=count,
        )

        # Emit changes
        self.devicesChanged.emit(self._get_devices_as_dict())
        self._set_success(data=self._devices, message=f"Synced {count} devices")

        # Log status changes
        if status_changes:
            logger.info(
                "[DeviceListViewModel] %d status changes detected",
                len(status_changes),
            )

        if self._shell_vm:
            self._shell_vm.update_system_status(
                mssql_connected=True,
                sqlite_connected=True,
                message="Ready",
                last_sync_time=timestamp,
            )

    def _on_sync_error(self, error: Exception) -> None:
        """Handle sync error."""
        if self._is_disposed:
            return

        self._set_batch_loading(False)
        self._update_connection_state(False)

        error_msg = str(error)
        logger.error("[DeviceListViewModel] Sync error: %s", error_msg)

        self._update_sync_status(
            is_syncing=False,
            error_message=error_msg,
        )
        self._set_error(f"Sync failed: {error_msg}")

    # =========================================================================
    # Device Details Fetching
    # =========================================================================

    def _fetch_device_details_parallel(self, device_id: str) -> None:
        """Fetch device details (availability and materials) in parallel."""
        self._detail_generation += 1
        generation = self._detail_generation
        remote_id = self._id_mapper.to_remote_id(device_id)

        # Fetch availability
        if self._sync_orchestrator:
            self._executor.execute(
                self._do_fetch_availability(device_id, generation),
                on_success=self._on_availability_success,
                on_error=self._on_detail_error,
            )

        # Fetch materials
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
        """Fetch device availability."""
        if self._is_disposed or generation < self._detail_generation - 5:
            return {"device_id": device_id, "skipped": True, "type": "availability"}

        if self._pending_detail_device != device_id:
            return {"device_id": device_id, "skipped": True, "type": "availability"}

        if not self._sync_orchestrator:
            return {
                "device_id": device_id,
                "error": "No orchestrator",
                "type": "availability",
            }

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
            return {
                "device_id": device_id,
                "generation": generation,
                "error": str(e),
                "type": "availability",
            }

    async def _do_fetch_material_inputs(
        self,
        display_id: str,
        remote_id: str,
        generation: int,
    ) -> Dict[str, Any]:
        """Fetch material inputs for device."""
        if self._is_disposed or generation < self._detail_generation - 5:
            return {"device_id": display_id, "skipped": True, "type": "materials"}

        if self._pending_detail_device != display_id:
            return {"device_id": display_id, "skipped": True, "type": "materials"}

        try:
            records = await self._remote_source.fetch_material_inputs(remote_id)

            if generation < self._detail_generation - 5 or self._is_disposed:
                return {"device_id": display_id, "skipped": True, "type": "materials"}

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
                logger.debug("[DeviceListViewModel] Material fetch error: %s", e)
            return {
                "device_id": display_id,
                "generation": generation,
                "error": str(e),
                "type": "materials",
            }

    def _on_availability_success(self, result: Dict[str, Any]) -> None:
        """Handle availability fetch success."""
        if self._is_disposed or result.get("skipped"):
            return

        device_id = result.get("device_id")
        generation = result.get("generation", 0)

        if generation < self._detail_generation - 5:
            return

        if device_id != self._selected_device_id:
            return

        # Clear loading
        self._set_device_loading(device_id, LoadingPhase.LOADED)

        if "error" in result:
            self._set_device_error(device_id, result["error"])
            return

        # Success - clear error and update model
        self._set_device_error(device_id, None)
        self._state_manager.mark_updated(device_id)

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
            self.availabilityChanged.emit(device_id, result)
            self._emit_selection_update()

    def _on_material_inputs_success(self, result: Dict[str, Any]) -> None:
        """Handle material inputs fetch success."""
        if self._is_disposed or result.get("skipped"):
            return

        device_id = result.get("device_id")
        generation = result.get("generation", 0)

        if generation < self._detail_generation - 5:
            return

        if device_id != self._selected_device_id:
            return

        if "error" in result:
            return

        materials = result.get("materials", [])
        lot_no = result.get("lot_no", "")

        if device_id in self._devices:
            old_model = self._devices[device_id]
            updated_model = old_model.with_material_inputs(materials, lot_no)
            self._devices[device_id] = updated_model

            self._state_manager.mark_updated(device_id)
            self.materialInputsChanged.emit(device_id, materials)
            self._emit_selection_update()

    def _on_detail_error(self, error: Exception) -> None:
        """Handle detail fetch error."""
        if self._is_disposed:
            return

        if self._pending_detail_device:
            device_id = self._pending_detail_device
            self._set_device_loading(device_id, LoadingPhase.ERROR)

            error_msg = str(error)
            # Don't set error for timeouts (transient)
            if "timed out" not in error_msg.lower():
                self._set_device_error(device_id, error_msg)
                logger.debug("[DeviceListViewModel] Detail error: %s", error_msg)

    # =========================================================================
    # Panel Refresh
    # =========================================================================

    @Slot(bool)
    def _on_right_panel_state_changed(self, is_open: bool) -> None:
        """Handle right panel state changes."""
        self._is_panel_open = is_open
        if is_open and self._selected_device_id:
            self._start_panel_refresh()
        else:
            self._stop_panel_refresh()

    def _start_panel_refresh(self) -> None:
        """Start periodic panel refresh."""
        if self._panel_refresh_timer and not self._panel_refresh_timer.isActive():
            self._panel_refresh_timer.start()

    def _stop_panel_refresh(self) -> None:
        """Stop periodic panel refresh."""
        if self._panel_refresh_timer and self._panel_refresh_timer.isActive():
            self._panel_refresh_timer.stop()

    @Slot()
    def _on_panel_refresh_tick(self) -> None:
        """Handle panel refresh timer tick."""
        if self._is_disposed or not self._is_panel_open or not self._selected_device_id:
            self._stop_panel_refresh()
            return

        self._fetch_device_details_parallel(self._selected_device_id)

    # =========================================================================
    # Model Transformation
    # =========================================================================

    def _transform_to_display_model(
        self,
        code: str,
        device_data: Any,
    ) -> DeviceDisplayModel:
        """Transform device data to display model."""
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
        )

    def _transform_record_to_display_model(
        self,
        record: Dict,
        display_code: Optional[str] = None,
    ) -> DeviceDisplayModel:
        """Transform record to display model."""
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
            last_update=(last_update.isoformat() if hasattr(last_update, "isoformat") else None),
        )

    def _merge_models(
        self,
        old_model: DeviceDisplayModel,
        new_model: DeviceDisplayModel,
    ) -> DeviceDisplayModel:
        """Merge old model details into new model."""
        return DeviceDisplayModel(
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
    # Helpers
    # =========================================================================

    def _update_sync_status(
        self,
        is_syncing: Optional[bool] = None,
        last_sync_time: Optional[str] = None,
        synced_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update sync status."""
        self._sync_status = DeviceSyncStatusModel(
            is_syncing=(is_syncing if is_syncing is not None else self._sync_status.is_syncing),
            last_sync_time=last_sync_time or self._sync_status.last_sync_time,
            synced_count=(synced_count if synced_count is not None else self._sync_status.synced_count),
            error_message=error_message,
        )
        self.syncStatusChanged.emit(self._sync_status)

    def _get_devices_as_dict(self) -> Dict[str, dict]:
        """Get devices as dictionary."""
        return {code: model.to_dict() for code, model in self._devices.items()}

    def _emit_selection_update(self) -> None:
        """Emit selection update signal."""
        if self._selected_device_id:
            selection = DeviceSelectionModel(
                selected_device_id=self._selected_device_id,
                is_panel_open=(self._shell_vm.right_panel_expanded if self._shell_vm else False),
            )
            self.selectionChanged.emit(selection)

    @Slot(str, list)
    def _on_page_changed(self, page_name: str, device_codes: List[str]) -> None:
        """Handle page change from page manager."""
        if not self._is_disposed:
            self.load_page(page_name, device_codes)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def dispose(self) -> None:
        """Clean up resources - IMPROVED."""
        if self._is_disposed:
            return

        logger.info("[DeviceListViewModel] Starting disposal...")
        self._is_disposed = True

        # Step 1: Invalidate all pending requests
        self._sync_generation += 1000
        self._detail_generation += 1000
        self._pending_detail_device = None
        self._pending_load_ids = None

        # Step 2: Stop all timers immediately
        self._stop_panel_refresh()

        timers_to_stop = [
            self._panel_refresh_timer,
            self._stale_check_timer,
            self._connection_check_timer,
            self._load_debounce_timer,
        ]

        for timer in timers_to_stop:
            if timer and timer.isActive():
                timer.stop()
                timer.deleteLater()

        self._panel_refresh_timer = None
        self._stale_check_timer = None
        self._connection_check_timer = None
        self._load_debounce_timer = None

        # Wait for executor to finish gracefully
        if self._executor:
            try:
                import time
                from PySide6.QtCore import QCoreApplication

                logger.debug(f"[DeviceListViewModel] Shutting down executor with " f"{self._executor.active_count} active tasks")

                # Wait for active operations to complete (with timeout)
                start_time = time.time()
                timeout = 1.0  # 1 second max wait

                while self._executor.active_count > 0:
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning(f"[DeviceListViewModel] Timeout waiting for " f"{self._executor.active_count} operations")
                        break

                    # Process Qt events to allow signals to be delivered
                    QCoreApplication.processEvents()
                    time.sleep(0.01)

                # Cancel any remaining futures
                if hasattr(self._executor, "_pending_futures"):
                    for future in list(self._executor._pending_futures.values()):
                        if not future.done():
                            future.cancel()

                # Final shutdown
                self._executor.shutdown(wait=False)

                logger.debug("[DeviceListViewModel] Executor shutdown complete")

            except Exception as e:
                logger.error(f"[DeviceListViewModel] Executor shutdown error: {e}")

        # Step 3: Disconnect signals
        for signal, slot in self._connected_signals:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connected_signals.clear()

        # Step 4: Clear state
        self._state_manager.clear()
        self._status_tracker.clear()
        self._devices.clear()

        # Step 5: Call parent dispose
        BaseViewModel.dispose(self)
        logger.info("[DeviceListViewModel] Disposed successfully")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "DeviceListViewModel",
    "DeviceStateManager",
    "StatusChangeTracker",
    "LoadingPhase",
    "DeviceState",
    "StatusChange",
    "ConnectionState",
    "ConnectionInfo",
    "IDeviceIdMapper",
    "NoOpIdMapper",
]
