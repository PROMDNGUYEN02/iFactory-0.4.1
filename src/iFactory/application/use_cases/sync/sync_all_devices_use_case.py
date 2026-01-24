"""
Sync All Devices Use Case.

Orchestrates the synchronization of device statuses from the remote
data source (MSSQL) to the local repository (SQLite).

This use case ensures that data from the outside world is converted
into valid Domain Entities before persistence.
"""

import logging
from typing import List, Optional

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.infrastructure.persistence.data_sources.mssql_data_source import MssqlDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesUseCase:
    """
    Use case: Synchronize all device statuses.

    Responsibilities:
    1. Fetch raw data from the Remote Data Source (Infrastructure).
    2. Convert raw data to Domain Entities (Business Logic).
    3. Persist valid entities via the Repository (Infrastructure).

    This ensures that invalid data cannot enter the domain and that
    all business invariants are enforced during the sync process.
    """

    def __init__(
        self,
        remote_source: MssqlDataSource,
        device_repository: DeviceRepository,
    ):
        """
        Initialize the use case.

        Args:
            remote_source: Data source for fetching remote records.
            device_repository: Repository for persisting domain entities.
        """
        self._remote_source = remote_source
        self._device_repo = device_repository

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        """
        Execute the synchronization workflow.

        Args:
            equipment_codes: Optional list of equipment codes to filter.
                             If None, syncs all available devices.

        Returns:
            The number of devices successfully synced.
        """
        logger.info("[SyncAllDevicesUseCase] Starting synchronization...")

        # 1. Fetch raw data (Technical operation)
        # Note: remote_source.fetch_latest_status is expected to return
        # an iterable of objects with 'equip_code', 'equip_status', 'last_update'.
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"[SyncAllDevicesUseCase] Remote fetch failed: {e}", exc_info=True)
            return 0

        if not remote_records:
            logger.info("[SyncAllDevicesUseCase] No records returned from remote source.")
            return 0

        # 2. Convert to Domain Entities (Business Logic)
        # Using the factory method ensures Value Objects are created correctly.
        devices: List[Device] = []
        skipped_count = 0

        for record in remote_records:
            try:
                # Extract and normalize data from remote record
                code = getattr(record, "equip_code", None)
                status_code = getattr(record, "equip_status", None)
                last_update = getattr(record, "last_update", None)

                if not code:
                    skipped_count += 1
                    continue

                # Device.create() enforces Value Object invariants (EquipmentCode, Status)
                device = Device.create(
                    code=str(code),
                    status=str(status_code) if status_code else "0",
                    last_update=last_update,
                )
                devices.append(device)
            except ValueError as ve:
                # Domain validation failed (e.g. invalid equipment code)
                logger.warning(f"[SyncAllDevicesUseCase] Skipping invalid record: {ve}")
                skipped_count += 1
            except Exception as e:
                logger.warning(f"[SyncAllDevicesUseCase] Unexpected error processing record: {e}")
                skipped_count += 1

        if skipped_count > 0:
            logger.warning(f"[SyncAllDevicesUseCase] Skipped {skipped_count} invalid records.")

        if not devices:
            logger.warning("[SyncAllDevicesUseCase] No valid devices to sync.")
            return 0

        # 3. Persist (Technical operation)
        try:
            count = await self._device_repo.save_many(devices)
            logger.info(f"[SyncAllDevicesUseCase] Successfully synced {count} devices.")
            return count
        except Exception as e:
            logger.error(f"[SyncAllDevicesUseCase] Persistence failed: {e}", exc_info=True)
            raise
