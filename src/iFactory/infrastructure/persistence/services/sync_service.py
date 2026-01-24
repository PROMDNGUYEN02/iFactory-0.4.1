"""
Sync service - Orchestrates data synchronization.
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy import text
from iFactory.domain import Device, DeviceHistory, MaterialInput, TimeRange
from iFactory.infrastructure.database import DatabaseOrchestrator
from ..data_sources import MssqlDataSource
from ..repositories import (
    SqliteDeviceRepository,
    SqliteStatusRepository,
    SqliteInputRepository,
    SqliteSyncMetadataRepository,
)
from ..utils import load_layout, extract_codes_from_layout

__all__ = ["SyncService", "SyncResult", "SyncAllResult"]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncResult:
    """Result of a sync operation."""

    hot_count: int = 0
    cold_count: int = 0
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    skipped_count: int = 0

    @property
    def total(self) -> int:
        return self.hot_count + self.cold_count

    @classmethod
    def failure(cls, error: str) -> "SyncResult":
        return cls(success=False, error=error)


@dataclass(slots=True)
class SyncAllResult:
    """Combined sync result."""

    status: SyncResult = field(default_factory=SyncResult)
    input: SyncResult = field(default_factory=SyncResult)
    history: SyncResult = field(default_factory=SyncResult)
    input_history: SyncResult = field(default_factory=SyncResult)

    @property
    def success(self) -> bool:
        return all((r.success for r in (self.status, self.input, self.history, self.input_history)))

    @property
    def total_records(self) -> int:
        return sum((r.total for r in (self.status, self.input, self.history, self.input_history)))


class SyncService:
    """
    Service for synchronizing data between MSSQL and SQLite.

    Sync paths:
        - Hot sync: MSSQL → SQLite hot store (latest state)
        - Cold sync: MSSQL → SQLite cold store (history)

    Refactored to be purely technical:
        - Removes pre-validation of business rules (e.g., time ranges).
        - Passes raw data directly to Domain Entities.
        - Delegates errors/decisions to Domain/Repository layers.
    """

    DEFAULT_HISTORY_HOURS = 168
    __slots__ = (
        "_db",
        "_data_source",
        "_device_repo",
        "_status_repo",
        "_input_repo",
        "_sync_meta_repo",
        "_initialized",
        "_last_history_sync",
        "_history_interval",
    )

    def __init__(
        self,
        db: DatabaseOrchestrator,
        data_source: Optional[MssqlDataSource] = None,
        history_interval: int = 300,
    ):
        """
        Initialize sync service.

        Args:
            db: Database orchestrator
            data_source: MSSQL data source (created from db if not provided)
            history_interval: Minimum seconds between history syncs
        """
        self._db = db
        self._data_source = data_source or MssqlDataSource(engine=db.mssql)
        self._device_repo = SqliteDeviceRepository(db.hot)
        self._status_repo = SqliteStatusRepository(db.hot, db.cold)
        self._input_repo = SqliteInputRepository(db.hot, db.cold)
        self._sync_meta_repo = SqliteSyncMetadataRepository(db.hot)
        self._initialized = False
        self._last_history_sync: Optional[datetime] = None
        self._history_interval = history_interval

    async def initialize(self) -> None:
        """Initialize all repositories."""
        if self._initialized:
            return
        await asyncio.gather(
            self._device_repo.initialize(),
            self._status_repo.initialize(),
            self._input_repo.initialize(),
            self._sync_meta_repo.initialize(),
        )
        self._initialized = True
        logger.info("[SyncService] Initialized")

    async def get_device_codes(self) -> List[str]:
        """Get device codes from layout."""
        layout = await asyncio.to_thread(load_layout)
        return extract_codes_from_layout(layout)

    async def sync_status_hot(self, codes: Optional[List[str]] = None) -> SyncResult:
        """Sync latest status: MSSQL → Hot store."""
        import time

        start = time.perf_counter()
        try:
            codes = codes or await self.get_device_codes()
            if not codes:
                return SyncResult()
            remote_records = await self._data_source.fetch_latest_status(codes)
            if not remote_records:
                return SyncResult()
            # Map raw remote records to Domain Entities using factory
            devices = [Device.create(code=r.equip_code, status=r.equip_status, last_update=r.last_update) for r in remote_records]
            count = await self._device_repo.save_many(devices)
            duration = (time.perf_counter() - start) * 1000
            return SyncResult(hot_count=count, duration_ms=duration)
        except Exception as e:
            logger.error(f"Status hot sync error: {e}", exc_info=True)
            return SyncResult.failure(str(e))

    async def sync_input_hot(self, codes: Optional[List[str]] = None) -> SyncResult:
        """Sync latest input: MSSQL → Hot store."""
        import time

        start = time.perf_counter()
        try:
            codes = codes or await self.get_device_codes()
            if not codes:
                logger.warning("[sync_input_hot] No device codes found")
                return SyncResult()
            remote_records = await self._data_source.fetch_latest_input(codes)
            if not remote_records:
                return SyncResult()
            logger.info(f"[sync_input_hot] Fetched {len(remote_records)} records from MSSQL")
            inputs = [
                MaterialInput(
                    equip_code=r.equip_code,
                    material_batch=r.material_batch,
                    feeding_time=r.feeding_time,
                )
                for r in remote_records
                if r.feeding_time
            ]
            filtered_out = len(remote_records) - len(inputs)
            if filtered_out > 0:
                logger.warning(f"[sync_input_hot] Filtered out {filtered_out} records (no feeding_time)")
            logger.info(f"[sync_input_hot] Saving {len(inputs)} inputs to hot store")
            count = await self._input_repo.save_latest_many(inputs)
            logger.info(f"[sync_input_hot] Saved {count} inputs successfully")
            duration = (time.perf_counter() - start) * 1000
            return SyncResult(hot_count=count, duration_ms=duration)
        except Exception as e:
            logger.error(f"Input hot sync error: {e}", exc_info=True)
            return SyncResult.failure(str(e))

    async def sync_history_cold(
        self,
        codes: Optional[List[str]] = None,
        hours: int = DEFAULT_HISTORY_HOURS,
        force: bool = False,
    ) -> SyncResult:
        """
        Sync status history: MSSQL → Cold store.

        Refactored: Removed business logic validation (start <= end).
        Delegates data integrity to Domain Entities and Repositories.
        """
        if not force and self._last_history_sync:
            elapsed = (datetime.now() - self._last_history_sync).total_seconds()
            if elapsed < self._history_interval:
                logger.debug(f"Skipping history sync, last sync {elapsed:.0f}s ago")
                return SyncResult()
        import time

        start_time = time.perf_counter()
        try:
            codes = codes or await self.get_device_codes()
            if not codes:
                return SyncResult()
            logger.info(f"[Cold] Starting history sync for {len(codes)} devices")
            since = datetime.now() - timedelta(hours=hours)
            remote_records = await self._data_source.fetch_status_since(since, codes)
            logger.info(f"[sync_history_cold] Fetched {len(remote_records)} status records since {since}")
            if not remote_records:
                logger.warning("[sync_history_cold] No records from MSSQL")
                self._last_history_sync = datetime.now()
                return SyncResult()

            periods = []
            skipped_count = 0
            now = datetime.now()

            # Pure technical iteration. Let Domain entities validate invariants.
            for r in remote_records:
                try:
                    # Skip records with invalid/missing timestamps
                    if r.start_time is None:
                        skipped_count += 1
                        logger.debug(f"Skipping record for {r.equip_code if hasattr(r, 'equip_code') else 'Unknown'}: start_time is None")
                        continue

                    end_time = r.end_time or now
                    # Use safe_create to handle edge cases
                    period = DeviceHistory.create(
                        code=r.equip_code,
                        status=r.equip_status,
                        start=r.start_time,
                        end=end_time,
                    )
                    periods.append(period)
                except Exception as e:
                    # Catch technical errors (e.g. invalid status code, None start_time) to preserve batch
                    skipped_count += 1
                    logger.debug(f"Skipping record for {r.equip_code if hasattr(r, 'equip_code') else 'Unknown'}: {e}")
                    continue

            if skipped_count > 0:
                logger.warning(f"[sync_history_cold] Skipped {skipped_count} records (invalid data)")

            if not periods:
                logger.warning("[sync_history_cold] No valid periods to save")
                self._last_history_sync = datetime.now()
                return SyncResult(skipped_count=skipped_count)

            logger.info(f"[sync_history_cold] Saving {len(periods)} periods to cold store")
            count = await self._status_repo.save_many_to_history(periods)
            logger.info(f"[sync_history_cold] Saved {count} periods successfully")
            self._last_history_sync = datetime.now()
            duration = (time.perf_counter() - start_time) * 1000
            logger.info(f"[Cold] Synced {count} status history records in {duration:.0f}ms")
            return SyncResult(cold_count=count, duration_ms=duration, skipped_count=skipped_count)
        except Exception as e:
            logger.error(f"History cold sync error: {e}", exc_info=True)
            return SyncResult.failure(str(e))

    async def sync_input_history_cold(self, codes: Optional[List[str]] = None, hours: int = DEFAULT_HISTORY_HOURS) -> SyncResult:
        """Sync input history: MSSQL → Cold store."""
        import time

        start = time.perf_counter()
        try:
            codes = codes or await self.get_device_codes()
            if not codes:
                return SyncResult()
            since = datetime.now() - timedelta(hours=hours)
            remote_records = await self._data_source.fetch_input_since(since, codes)
            if not remote_records:
                return SyncResult()
            inputs = [
                MaterialInput(
                    equip_code=r.equip_code,
                    material_batch=r.material_batch,
                    feeding_time=r.feeding_time,
                )
                for r in remote_records
                if r.feeding_time
            ]
            count = await self._input_repo.save_many_to_history(inputs)
            duration = (time.perf_counter() - start) * 1000
            logger.info(f"[Cold] Synced {count} input history records")
            return SyncResult(cold_count=count, duration_ms=duration)
        except Exception as e:
            logger.error(f"Input history cold sync error: {e}", exc_info=True)
            return SyncResult.failure(str(e))

    async def checkpoint_cold_wal(self) -> None:
        """Checkpoint cold store WAL."""
        await self._db.cold.checkpoint("TRUNCATE")

    async def sync_all(
        self,
        codes: Optional[List[str]] = None,
        include_history: bool = True,
        history_hours: int = DEFAULT_HISTORY_HOURS,
    ) -> SyncAllResult:
        """Sync all data with parallel optimization."""
        status_task = asyncio.create_task(self.sync_status_hot(codes))
        input_task = asyncio.create_task(self.sync_input_hot(codes))
        (status, input_result) = await asyncio.gather(status_task, input_task)
        history = SyncResult()
        input_history = SyncResult()
        if include_history:
            history_task = asyncio.create_task(self.sync_history_cold(codes, hours=history_hours))
            input_hist_task = asyncio.create_task(self.sync_input_history_cold(codes, hours=history_hours))
            (history, input_history) = await asyncio.gather(history_task, input_hist_task)
            await self.checkpoint_cold_wal()
        return SyncAllResult(
            status=status,
            input=input_result,
            history=history,
            input_history=input_history,
        )

    async def get_all_devices(self) -> List[Device]:
        """Get all devices from hot store."""
        return list(await self._device_repo.get_all())

    async def get_device_status_history(self, code: str, days: int = 7) -> List[DeviceHistory]:
        """Get status history for a device."""
        time_range = TimeRange.last_days(days)
        return list(await self._status_repo.get_history(code, time_range))

    async def get_latest_status(self, codes: Optional[List[str]] = None) -> List[Device]:
        """Get latest status from hot store."""
        return list(await self._device_repo.get_all(codes))

    async def get_latest_input(self, codes: Optional[List[str]] = None) -> List[MaterialInput]:
        """Get latest input from hot store."""
        return list(await self._input_repo.get_all_latest(codes))

    async def get_status_history(self, code: str, days: int = 7) -> List[DeviceHistory]:
        """Get status history for a device."""
        time_range = TimeRange.last_days(days)
        return list(await self._status_repo.get_history(code, time_range))

    async def get_input_history(self, code: str, days: int = 7) -> List[MaterialInput]:
        """Get input history for a device."""
        time_range = TimeRange.last_days(days)
        return list(await self._input_repo.get_history(code, time_range))
