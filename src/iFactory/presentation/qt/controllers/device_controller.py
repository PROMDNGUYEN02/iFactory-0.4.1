"""
Device Controller - Refactored to orchestration only.

Changes:
- Removed all complex mapping/formatting logic.
- Delegated DTO-to-Dict conversion to DevicePresenter.
- Simplified refresh flow to: UseCase -> Presenter -> View.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from PySide6.QtCore import QObject, Signal
from iFactory.shared.utils.profiler import profile_block, profile_async_method

if TYPE_CHECKING:
    from iFactory.application.services.__init__1 import DeviceDataService
    from iFactory.presentation.qt.presenters import DevicePresenter
    from iFactory.infrastructure.persistence.services import SyncService
logger = logging.getLogger(__name__)


class DeviceController(QObject):
    """
    Controller for device-related actions.

    Responsibilities (Refactored):
        - Handle device status requests (Orchestration)
        - Coordinate device data updates (Orchestration)
        - Handle async device operations (Orchestration)
        - Trigger sync from MSSQL (Orchestration)
        - Cache management for fast startup (Orchestration)
    """

    device_selected = Signal(str, str)
    status_updated = Signal(dict)
    gantt_data_ready = Signal(str, list, object, object)
    error_occurred = Signal(str)
    sync_completed = Signal(int)
    cache_loaded = Signal(int)
    refresh_started = Signal()
    refresh_complete = Signal()

    def __init__(
        self,
        device_service: Optional["DeviceDataService"] = None,
        signal_adapter=None,
        async_executor=None,
        sync_service: Optional["SyncService"] = None,
        device_presenter: Optional["DevicePresenter"] = None,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize device controller.

        Args:
            device_service: Device data application service
            signal_adapter: Qt signal adapter
            async_executor: Async task executor
            sync_service: Sync service for MSSQL sync (optional)
            device_presenter: Presenter for formatting data
            parent: Parent QObject
        """
        super().__init__(parent)
        self._device_service = device_service
        self._signal_adapter = signal_adapter
        self._async_executor = async_executor
        self._sync_service = sync_service
        self._presenter = device_presenter  # Injected
        self._current_device: Optional[str] = None
        self._last_sync_success = False
        self._sync_in_progress = False
        self._cached_statuses: Dict[str, Dict[str, Any]] = {}
        self._last_cache_load: Optional[datetime] = None
        self._last_refresh_time: Optional[datetime] = None
        self._cache_valid = False
        logger.info("[DeviceController] Created (Refactored)")

    def set_sync_service(self, sync_service: "SyncService") -> None:
        """Set sync service (for late injection)."""
        self._sync_service = sync_service
        logger.debug("[DeviceController] Sync service set")

    @property
    def has_sync_service(self) -> bool:
        """Check if sync service is available."""
        return self._sync_service is not None

    async def load_from_cache(self) -> int:
        """
        Load device statuses from local cache/database.

        This is FAST and should be called first during startup.
        Does NOT sync from remote - just reads local data.

        Returns:
            Number of devices loaded from cache
        """
        if not self._device_service:
            logger.debug("[DeviceController] No device service for cache load")
            return 0
        try:
            with profile_block("Load from local cache"):
                statuses = await self._get_local_statuses()
            if statuses:
                # Use Presenter to format data for emission
                if self._presenter:
                    formatted = self._presenter.format_for_update(statuses)
                    self._cached_statuses = formatted
                else:
                    # Fallback if presenter not injected (should not happen in DI)
                    self._cached_statuses = statuses

                self._last_cache_load = datetime.now()
                self._cache_valid = True
                logger.info(f"[DeviceController] Loaded {len(statuses)} devices from cache")
                if self._signal_adapter:
                    status_dict = self._cached_statuses  # Already formatted by presenter
                    self._signal_adapter.emit_device_statuses(status_dict)
                self.cache_loaded.emit(len(statuses))
                return len(statuses)
            else:
                logger.debug("[DeviceController] No cached data available")
                return 0
        except Exception as e:
            logger.debug(f"[DeviceController] Cache load failed: {e}")
            return 0

    async def _get_local_statuses(self) -> Dict[str, Any]:
        """
        Get statuses from local database without syncing.

        Returns:
            Dictionary of device statuses from local DB
        """
        if not self._device_service:
            return {}
        try:
            if hasattr(self._device_service, "get_cached_statuses"):
                return await self._device_service.get_cached_statuses()
            elif hasattr(self._device_service, "get_all_latest_status_local"):
                return await self._device_service.get_all_latest_status_local()
            elif hasattr(self._device_service, "get_all_latest_status"):
                return await self._device_service.get_all_latest_status()
            else:
                logger.warning("[DeviceController] No cache method available")
                return {}
        except Exception as e:
            logger.debug(f"[DeviceController] Local status fetch failed: {e}")
            return {}

    def get_cached_status(self, device_code: str) -> Optional[Dict[str, Any]]:
        """
        Get cached status for a single device.

        Args:
            device_code: Equipment code

        Returns:
            Cached status dict or None
        """
        return self._cached_statuses.get(device_code)

    def get_all_cached_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cached statuses.

        Returns:
            Copy of cached statuses dictionary
        """
        return self._cached_statuses.copy()

    @property
    def cache_count(self) -> int:
        """Get number of cached devices."""
        return len(self._cached_statuses)

    @property
    def is_cache_valid(self) -> bool:
        """Check if cache is valid and populated."""
        return self._cache_valid and len(self._cached_statuses) > 0

    def invalidate_cache(self) -> None:
        """Invalidate cache (force refresh on next load)."""
        self._cache_valid = False
        logger.debug("[DeviceController] Cache invalidated")

    async def handle_device_clicked(self, device_code: str, device_name: str) -> None:
        """Handle device click."""
        logger.debug(f"[DeviceController] Device clicked: {device_code}")
        self._current_device = device_code
        self.device_selected.emit(device_code, device_name)

    @profile_async_method(threshold_ms=100)
    async def refresh_all_devices(self, device_codes: Optional[List[str]] = None) -> int:
        """
        Refresh all device statuses from remote.

        This will:
        1. Sync from MSSQL to local DB (if sync service available)
        2. Read from local DB (Use Case)
        3. Convert DTOs to dict format using Presenter
        4. Emit to signal adapter
        5. Update cache

        Args:
            device_codes: Optional list of specific device codes to refresh

        Returns:
            Number of devices refreshed
        """
        if self._sync_in_progress:
            logger.debug("[DeviceController] Sync already in progress, skipping")
            return 0
        self._sync_in_progress = True
        self.refresh_started.emit()
        try:
            with profile_block("Sync from remote"):
                sync_count = await self._sync_from_remote(device_codes)
            if not self._device_service:
                logger.warning("[DeviceController] No device service available")
                return 0
            with profile_block("Read from local DB"):
                logger.debug("[DeviceController] Reading device statuses from local DB...")
                statuses = await self._device_service.get_all_latest_status(device_codes)
            if not statuses:
                if sync_count == 0:
                    logger.debug("[DeviceController] No device statuses found (sync may have failed)")
                else:
                    logger.warning(f"[DeviceController] Synced {sync_count} but no statuses read from DB")
                return 0

            # Delegate formatting to Presenter
            formatted_statuses = {}
            if self._presenter:
                formatted_statuses = self._presenter.format_for_update(statuses)
            else:
                # Defensive fallback, though Presenter should be injected
                logger.warning("[DeviceController] Presenter not available, using raw data")
                formatted_statuses = statuses

            self._cached_statuses = formatted_statuses
            self._last_refresh_time = datetime.now()
            self._cache_valid = True

            with profile_block("Emit formatted data"):
                if self._signal_adapter:
                    # Presenter ensures the dict format matches what SignalAdapter/View expects
                    self._signal_adapter.emit_device_statuses(formatted_statuses)

            logger.info(f"[DeviceController] Refreshed {len(formatted_statuses)} devices")
            self.sync_completed.emit(len(formatted_statuses))
            self.refresh_complete.emit()
            return len(formatted_statuses)
        except Exception as e:
            logger.error(f"[DeviceController] Refresh failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            return 0
        finally:
            self._sync_in_progress = False

    async def _sync_from_remote(self, device_codes: Optional[List[str]] = None) -> int:
        """
        Sync data from MSSQL to local SQLite.

        Returns:
            Number of devices synced
        """
        if not self._sync_service:
            logger.debug("[DeviceController] No sync service, skipping remote sync")
            return 0
        try:
            if not self._sync_service._initialized:
                await self._sync_service.initialize()
            result = await self._sync_service.sync_status_hot(device_codes)
            if result.success:
                if result.hot_count > 0:
                    logger.debug(f"[DeviceController] Synced {result.hot_count} devices in {result.duration_ms:.0f}ms")
                self._last_sync_success = True
                return result.hot_count
            else:
                logger.warning(f"[DeviceController] Sync failed: {result.error}")
                self._last_sync_success = False
                return 0
        except Exception as e:
            logger.error(f"[DeviceController] Sync error: {e}")
            self._last_sync_success = False
            return 0

    async def sync_devices(self, device_codes: Optional[List[str]] = None) -> int:
        """Alias for refresh_all_devices."""
        return await self.refresh_all_devices(device_codes)

    async def sync_and_refresh(self, include_history: bool = False) -> Dict[str, Any]:
        """
        Full sync and refresh operation.

        Args:
            include_history: Also sync history data to cold store

        Returns:
            Sync result summary
        """
        result = {
            "status_count": 0,
            "input_count": 0,
            "history_count": 0,
            "success": False,
        }
        if not self._sync_service:
            logger.warning("[DeviceController] No sync service available")
            return result
        try:
            if not self._sync_service._initialized:
                await self._sync_service.initialize()
            sync_result = await self._sync_service.sync_all(include_history=include_history)
            result["status_count"] = sync_result.status.hot_count
            result["input_count"] = sync_result.input.hot_count
            result["history_count"] = sync_result.history.cold_count
            result["success"] = sync_result.success
            if sync_result.success:
                await self.refresh_all_devices()
            return result
        except Exception as e:
            logger.error(f"[DeviceController] Sync and refresh failed: {e}")
            return result

    async def load_device_gantt(self, device_code: str) -> None:
        """Load Gantt data for device."""
        if not self._device_service:
            logger.warning("[DeviceController] No device service for Gantt")
            return
        try:
            logger.debug(f"[DeviceController] Loading Gantt for {device_code}")
            if self._sync_service:
                try:
                    await self._sync_service.sync_history_cold(codes=[device_code], hours=24, force=False)
                except Exception as e:
                    logger.warning(f"[DeviceController] History sync skipped: {e}")
            gantt_result = await self._device_service.generate_gantt_segments(device_code, days=1)
            if gantt_result and self._signal_adapter:
                self._signal_adapter.emit_gantt_data(
                    device_code,
                    gantt_result.get("segments", []),
                    gantt_result.get("start"),
                    gantt_result.get("end"),
                )
                logger.debug(f"[DeviceController] Gantt loaded for {device_code}")
            else:
                logger.warning(f"[DeviceController] No Gantt data for {device_code}")
        except Exception as e:
            logger.error(f"[DeviceController] Gantt load failed: {e}")

    def shutdown(self) -> None:
        """Shutdown controller."""
        self._sync_in_progress = False
        self._cached_statuses.clear()
        self._cache_valid = False
        logger.info("[DeviceController] Shutdown")


__all__ = ["DeviceController"]
