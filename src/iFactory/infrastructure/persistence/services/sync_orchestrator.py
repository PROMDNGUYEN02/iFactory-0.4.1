"""
Sync orchestrator - Scheduled synchronization tasks.

Manages periodic data synchronization between MSSQL and SQLite.
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Optional
from .sync_service import SyncService
from iFactory.infrastructure.database import DatabaseOrchestrator
from iFactory.infrastructure.persistence.types.sync_metadata import SyncMetadata

__all__ = ["SyncOrchestrator"]
logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """
    Orchestrates periodic data synchronization.
    """

    __slots__ = (
        "_db",
        "_sync_service",
        "_status_interval",
        "_input_interval",
        "_history_interval",
        "_running",
        "_tasks",
        "_device_codes",
    )

    def __init__(
        self,
        db: DatabaseOrchestrator,
        sync_service: SyncService,
        status_interval: float = 3.0,
        input_interval: float = 3.0,
        history_interval: float = 5.0,
        interval_seconds: int = 60,
    ):
        """
        Initialize orchestrator.

        Args:
            db: Database orchestrator
            sync_service: SyncService instance (created if None, but should be injected)
            status_interval: Seconds between status syncs
            input_interval: Seconds between input syncs
            history_interval: Seconds between history syncs
        """
        self._db = db
        if sync_service is not None:
            self._sync_service = sync_service
        else:
            logger.warning(
                "[SyncOrchestrator] SyncService not injected, creating new instance (this is inefficient - should be injected from app_container)"
            )
            self._sync_service = SyncService(db)
        self._status_interval = status_interval
        self._input_interval = input_interval
        self._history_interval = history_interval
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._device_codes: List[str] = []

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"SyncOrchestrator started with {self._interval_seconds}s interval.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SyncOrchestrator stopped.")

    async def _run_loop(self):
        while self._running:
            try:
                await self._sync_service.sync_all_devices()
            except Exception as e:
                logger.error(f"SyncOrchestrator encountered error: {e}")
            await asyncio.sleep(self._interval_seconds)

    async def _sync_status(self) -> None:
        """Sync latest status: MSSQL → Hot store."""
        try:
            result = await self._sync_service.sync_status_hot(self._device_codes)
            if result.success and result.hot_count > 0:
                logger.debug(f"[SyncOrchestrator] Status: {result.hot_count} records")
        except Exception as e:
            logger.error(f"[SyncOrchestrator] Status sync failed: {e}")

    async def _sync_input(self) -> None:
        """Sync latest input: MSSQL → Hot store."""
        try:
            result = await self._sync_service.sync_input_hot(self._device_codes)
            if result.success and result.hot_count > 0:
                logger.debug(f"[SyncOrchestrator] Input: {result.hot_count} records")
        except Exception as e:
            logger.error(f"[SyncOrchestrator] Input sync failed: {e}")

    async def _sync_status_history(self) -> None:
        """Sync status history: MSSQL → Cold store."""
        try:
            result = await self._sync_service.sync_history_cold(self._device_codes, hours=24, force=True)
            if result.success and result.cold_count > 0:
                logger.info(f"[SyncOrchestrator] Status history: {result.cold_count} records (skipped: {result.skipped_count})")
        except Exception as e:
            logger.error(f"[SyncOrchestrator] Status history sync failed: {e}")

    async def _sync_input_history(self) -> None:
        """Sync input history: MSSQL → Cold store."""
        try:
            result = await self._sync_service.sync_input_history_cold(self._device_codes, hours=24)
            if result.success and result.cold_count > 0:
                logger.info(f"[SyncOrchestrator] Input history: {result.cold_count} records")
        except Exception as e:
            logger.error(f"[SyncOrchestrator] Input history sync failed: {e}")

    async def force_sync(self, include_history: bool = True) -> None:
        """Force immediate sync of all data."""
        logger.info("[SyncOrchestrator] Forcing full sync...")
        try:
            result = await self._sync_service.sync_all(self._device_codes, include_history=include_history)
            logger.info(
                f"[SyncOrchestrator] Force sync complete: status={result.status.hot_count}, input={result.input.hot_count}, history={result.history.cold_count}, input_history={result.input_history.cold_count}"
            )
        except Exception as e:
            logger.error(f"[SyncOrchestrator] Force sync failed: {e}", exc_info=True)

    async def force_sync_history(self, hours: int = 168) -> None:
        """
        Force sync history data only (default 7 days).

        Args:
            hours: Number of hours to sync back
        """
        logger.info(f"[SyncOrchestrator] Forcing history sync for last {hours} hours...")
        try:
            status_result = await self._sync_service.sync_history_cold(self._device_codes, hours=hours, force=True)
            input_result = await self._sync_service.sync_input_history_cold(self._device_codes, hours=hours)
            logger.info(f"[SyncOrchestrator] History sync complete: status={status_result.cold_count}, input={input_result.cold_count}")
        except Exception as e:
            logger.error(f"[SyncOrchestrator] History sync failed: {e}", exc_info=True)

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    @property
    def device_count(self) -> int:
        """Get number of tracked devices."""
        return len(self._device_codes)
