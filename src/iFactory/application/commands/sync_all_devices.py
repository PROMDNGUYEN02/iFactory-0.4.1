"""
Application Command: Sync All Devices from Remote Source.
Updates Hot Storage (latest) and Cold Storage (history).
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable, Any

from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Sync device data.
    - Hot Store: Latest device status
    - Cold Store: Status history for Gantt Chart
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
                    # 1. Parse Raw Data
                    raw_code = str(record.get("equip_code"))
                    raw_status = record.get("raw_status", "0")
                    timestamp = record.get("last_update") or datetime.now()

                    # 2. Construct Domain Value Objects
                    code_vo = EquipmentCode(raw_code)

                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except (ValueError, TypeError):
                        status_enum = MachineStatus.UNKNOWN

                    # 3. Update Hot Store - Latest device status
                    device_entity = Device(
                        equipment_code=code_vo,
                        current_status=status_enum,
                        last_updated_at=timestamp,
                        name=record.get("name"),
                        description=record.get("description"),
                    )
                    # Use 'devices' attribute for Hot Store
                    await uow.devices.save(device_entity)

                    # 4. Update Cold Store - Status history
                    # Use 'history' attribute for Cold Store
                    await self._handle_status_history(uow.history, code_vo, status_enum, timestamp)

                    count += 1

                except Exception as e:
                    logger.warning(f"Error processing record for {record.get('equip_code', 'unknown')}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Successfully synchronized {count} devices.")
        return count

    async def _execute_legacy(self, remote_records: List[dict]) -> int:
        """Execute with legacy single UoW (Hot Storage only fallback)."""
        count = 0
        async with self._uow as uow:
            for record in remote_records:
                try:
                    raw_code = str(record.get("equip_code"))
                    raw_status = record.get("raw_status", "0")
                    timestamp = record.get("last_update") or datetime.now()

                    code_vo = EquipmentCode(raw_code)
                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except (ValueError, TypeError):
                        status_enum = MachineStatus.UNKNOWN

                    device_entity = Device(
                        equipment_code=code_vo,
                        current_status=status_enum,
                        last_updated_at=timestamp,
                    )
                    await uow.devices.save(device_entity)

                    count += 1
                except Exception as e:
                    logger.warning(f"Error processing record for {record.get('equip_code', 'unknown')}: {e}")

            await uow.commit()

        # Also update cold storage if factory is available (and we used legacy hot sync)
        if self._cold_uow_factory and count > 0:
            await self._sync_cold_storage(remote_records)

        return count

    async def _sync_cold_storage(self, remote_records: List[dict]) -> None:
        """Sync history to cold storage separately."""
        async with self._cold_uow_factory() as cold_uow:
            for record in remote_records:
                try:
                    raw_code = str(record.get("equip_code"))
                    raw_status = record.get("raw_status", "0")
                    timestamp = record.get("last_update") or datetime.now()

                    code_vo = EquipmentCode(raw_code)
                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except (ValueError, TypeError):
                        status_enum = MachineStatus.UNKNOWN

                    await self._handle_status_history(cold_uow.history, code_vo, status_enum, timestamp)
                except Exception as e:
                    logger.debug(f"Cold storage sync skipped for {raw_code}: {e}")

            await cold_uow.commit()

    async def _handle_status_history(
        self,
        history_repo,
        code: EquipmentCode,
        new_status: MachineStatus,
        timestamp: datetime,
    ) -> None:
        """Track status history in Cold Storage."""
        try:
            # Fetch latest recorded status period for this device
            latest_period: Optional[StatusPeriod] = await history_repo.get_latest_status(code)

            # Case 1: No previous history -> Create initial period
            if latest_period is None:
                new_period = StatusPeriod(
                    equipment_code=code,
                    status=new_status,
                    time_range=TimeRange.starting_from(timestamp),
                )
                await history_repo.save_status_period(new_period)
                return

            # Case 2: Status has changed -> Close old, Open new
            if latest_period.status != new_status:
                # Close the previous period
                closed_period = latest_period.with_end_time(timestamp)
                await history_repo.save_status_period(closed_period)

                # Open the new period
                new_period = StatusPeriod(
                    equipment_code=code,
                    status=new_status,
                    time_range=TimeRange.starting_from(timestamp),
                )
                await history_repo.save_status_period(new_period)

                logger.debug(f"Status Changed [{code.value}]: {latest_period.status.name} -> {new_status.name}")

            # Case 3: Status unchanged -> Do nothing (period continues)

        except Exception as e:
            logger.debug(f"Status history handling skipped for {code.value}: {e}")
