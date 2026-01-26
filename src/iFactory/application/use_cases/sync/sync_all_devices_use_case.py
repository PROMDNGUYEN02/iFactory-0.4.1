"""
Sync All Devices Use Case.

Orchestrates the synchronization of device statuses from the remote
data source to the local repository using a transactional Unit of Work.

Conforms to Clean Architecture:
Depends ONLY on Application Interfaces and Domain Entities.
"""

import logging
from typing import List, Optional

from iFactory.domain.entities.device import Device
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesUseCase:
    """
    Use case: Synchronize all device statuses.

    Responsibilities:
    1. Fetch raw data from the Remote Data Source.
    2. Convert raw data to Domain Entities (ensuring business validation).
    3. Persist valid entities safely using the Unit of Work.
    """

    def __init__(
        self,
        remote_source: IRemoteDataSource,
        uow: IUnitOfWork,  # <-- FIX: Now accepts Unit of Work instead of direct repository
    ):
        self._remote_source = remote_source
        self._uow = uow

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        """
        Execute the synchronization workflow.
        Returns the number of devices successfully synced.
        """
        logger.info("[SyncAllDevicesUseCase] Starting synchronization...")

        # 1. Fetch raw data from interface
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"[SyncAllDevicesUseCase] Remote fetch failed: {e}", exc_info=True)
            return 0

        if not remote_records:
            logger.info("[SyncAllDevicesUseCase] No records returned from remote source.")
            return 0

        # 2. Convert raw dictionaries to Domain Entities
        devices: List[Device] = []
        skipped_count = 0

        for record in remote_records:
            try:
                code = record.get("equip_code")
                status_code = record.get("equip_status")
                last_update = record.get("last_update")

                if not code:
                    skipped_count += 1
                    continue

                # Device.create() enforces Domain Invariants
                device = Device.create(
                    code=str(code),
                    raw_status=str(status_code) if status_code else "0",
                    last_update=last_update,
                )
                devices.append(device)
            except ValueError as ve:
                logger.warning(f"[SyncAllDevicesUseCase] Skipping invalid record: {ve}")
                skipped_count += 1
            except Exception as e:
                logger.warning(f"[SyncAllDevicesUseCase] Unexpected error processing record: {e}")
                skipped_count += 1

        if skipped_count > 0:
            logger.warning(f"[SyncAllDevicesUseCase] Skipped {skipped_count} invalid records.")

        if not devices:
            return 0

        # 3. Persist via Unit of Work (Transactional Safety)
        try:
            async with self._uow as uow:
                # Assuming the repository has a save_many or fallback to looping save
                if hasattr(uow.devices, "save_many"):
                    count = await uow.devices.save_many(devices)
                else:
                    for d in devices:
                        await uow.devices.save(d)
                    count = len(devices)

                # Commit the transaction
                await uow.commit()

            logger.info(f"[SyncAllDevicesUseCase] Successfully synced {count} devices.")
            return count
        except Exception as e:
            logger.error(f"[SyncAllDevicesUseCase] Persistence failed: {e}", exc_info=True)
            raise
