"""
Application Command: Sync All Devices from Remote Source.
Updates Hot Storage (latest) and Cold Storage (history).
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable, Any
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Sync device data.
    - Hot Store: Latest device status
    - Cold Store: Status history for Gantt Chart

    Supports both:
    - Legacy mode: single uow (HotStorageUnitOfWork)
    - Dual mode: dual_uow_factory (DualStorageUnitOfWork)
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow: Any = None,  # Legacy: HotStorageUnitOfWork
        dual_uow_factory: Callable = None,  # New: Returns DualStorageUnitOfWork
        cold_uow_factory: Callable = None,  # Optional: For history only
    ):
        self._remote_source = remote_source
        self._uow = uow
        self._dual_uow_factory = dual_uow_factory
        self._cold_uow_factory = cold_uow_factory

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"Failed to fetch from remote source: {e}")
            return 0

        if not remote_records:
            return 0

        # Use dual UoW if available, otherwise fall back to legacy
        if self._dual_uow_factory:
            return await self._execute_dual_storage(remote_records)
        else:
            return await self._execute_legacy(remote_records)

    async def _execute_dual_storage(self, remote_records: List[dict]) -> int:
        """Execute with DualStorageUnitOfWork (Hot + Cold)."""
        count = 0
        async with self._dual_uow_factory() as uow:
            for record in remote_records:
                try:
                    code = str(record.get("equip_code"))
                    new_status = str(record.get("raw_status", "0"))
                    timestamp = record.get("last_update") or datetime.now()

                    # 1. Update Hot Store - Latest device status
                    device_entity = Device.create(
                        code=code,
                        raw_status=new_status,
                        last_update=timestamp,
                    )
                    await uow.devices.save(device_entity)

                    # 2. Update Cold Store - Status history
                    await self._handle_status_history(uow.history, code, new_status, timestamp)

                    count += 1

                except Exception as e:
                    logger.warning(f"Error processing record for " f"{record.get('equip_code', 'unknown')}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Successfully synchronized {count} devices.")
        return count

    async def _execute_legacy(self, remote_records: List[dict]) -> int:
        """Execute with legacy single UoW (backward compatibility)."""
        count = 0
        async with self._uow as uow:
            for record in remote_records:
                try:
                    code = str(record.get("equip_code"))
                    new_status = str(record.get("raw_status", "0"))
                    timestamp = record.get("last_update") or datetime.now()

                    # Update current device snapshot
                    device_entity = Device.create(
                        code=code,
                        raw_status=new_status,
                        last_update=timestamp,
                    )
                    await uow.devices.save(device_entity)

                    # Try to handle history if repository supports it
                    if hasattr(uow.devices, "get_active_period"):
                        await self._handle_status_history_legacy(uow.devices, code, new_status, timestamp)

                    count += 1

                except Exception as e:
                    logger.warning(f"Error processing record for " f"{record.get('equip_code', 'unknown')}: {e}")

            await uow.commit()

        # Also update cold storage if factory is available
        if self._cold_uow_factory and count > 0:
            await self._sync_cold_storage(remote_records)

        if count > 0:
            logger.info(f"[Sync] Successfully synchronized {count} devices.")
        return count

    async def _sync_cold_storage(self, remote_records: List[dict]) -> None:
        """Sync history to cold storage separately."""
        async with self._cold_uow_factory() as cold_uow:
            for record in remote_records:
                try:
                    code = str(record.get("equip_code"))
                    new_status = str(record.get("raw_status", "0"))
                    timestamp = record.get("last_update") or datetime.now()

                    await self._handle_status_history(cold_uow.history, code, new_status, timestamp)
                except Exception as e:
                    logger.debug(f"Cold storage sync skipped for {code}: {e}")

            await cold_uow.commit()

    async def _handle_status_history(
        self,
        history_repo,
        code: str,
        new_status: str,
        timestamp: datetime,
    ) -> None:
        """Track status history in Cold Storage."""
        try:
            active_period = await history_repo.get_active_period(code)
            new_status_int = self._parse_status_code(new_status)

            if active_period is None:
                # Case 1: No active period -> Create initial period
                new_period = StatusPeriod.create(
                    id=str(uuid4()),
                    code=code,
                    raw_status=new_status,
                    start=timestamp,
                    end=None,
                )
                await history_repo.add_period(new_period)

            elif active_period.status_code != new_status_int:
                # Case 2: Status changed -> Close old, open new
                closed_period = active_period.with_end_time(timestamp)
                await history_repo.update_period(closed_period)

                new_period = StatusPeriod.create(
                    id=str(uuid4()),
                    code=code,
                    raw_status=new_status,
                    start=timestamp,
                    end=None,
                )
                await history_repo.add_period(new_period)

                logger.debug(f"Status Changed [{code}]: " f"{active_period.status_name} -> {new_status}")

            # Case 3: Status unchanged -> Period continues

        except Exception as e:
            logger.debug(f"Status history handling skipped for {code}: {e}")

    async def _handle_status_history_legacy(
        self,
        devices_repo,
        code: str,
        new_status: str,
        timestamp: datetime,
    ) -> None:
        """Legacy history handling via devices repository."""
        try:
            active_period = await devices_repo.get_active_period(code)
            new_status_int = self._parse_status_code(new_status)

            if active_period is None:
                new_period = StatusPeriod.create(
                    id=str(uuid4()),
                    code=code,
                    raw_status=new_status,
                    start=timestamp,
                    end=None,
                )
                await devices_repo.add_period(new_period)

            elif active_period.status_code != new_status_int:
                closed_period = active_period.with_end_time(timestamp)
                await devices_repo.update_period(closed_period)

                new_period = StatusPeriod.create(
                    id=str(uuid4()),
                    code=code,
                    raw_status=new_status,
                    start=timestamp,
                    end=None,
                )
                await devices_repo.add_period(new_period)

        except Exception as e:
            logger.debug(f"Legacy history handling skipped for {code}: {e}")

    @staticmethod
    def _parse_status_code(raw_status: str | int) -> int:
        """Parse raw status to integer."""
        if isinstance(raw_status, int):
            return raw_status
        try:
            return int(raw_status)
        except (ValueError, TypeError):
            return 0
