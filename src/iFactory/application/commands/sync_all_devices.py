"""
Application Command: Sync All Devices from Remote Source.
Uses immutable Domain value objects following DDD patterns.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Sync device data and automatically create history for Gantt Chart.
    Uses Domain logic to ensure data integrity.
    """

    def __init__(self, remote_source: IRemoteDataSource, uow: AbstractUnitOfWork):
        self._remote_source = remote_source
        self._uow = uow

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"Failed to fetch from remote source: {e}")
            return 0

        if not remote_records:
            return 0

        count = 0
        async with self._uow as uow:
            for record in remote_records:
                try:
                    code = str(record.get("equip_code"))
                    new_status = str(record.get("raw_status", "0"))
                    timestamp = record.get("last_update") or datetime.now()

                    # 1. Update current device snapshot
                    device_entity = Device.create(
                        code=code,
                        raw_status=new_status,
                        last_update=timestamp,
                    )
                    await uow.devices.save(device_entity)

                    # 2. Handle status history for Gantt Chart
                    await self._handle_status_history(uow, code, new_status, timestamp)

                    count += 1

                except Exception as e:
                    logger.warning(f"Error processing record for {record.get('equip_code', 'unknown')}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Successfully synchronized {count} devices.")
        return count

    async def _handle_status_history(
        self,
        uow,
        code: str,
        new_status: str,
        timestamp: datetime,
    ) -> None:
        """
        Track status history using immutable StatusPeriod pattern.

        StatusPeriod is an immutable value object - we use with_end_time()
        to create a new instance rather than mutating the existing one.
        """
        if not hasattr(uow.devices, "get_active_period"):
            return

        try:
            active_period = await uow.devices.get_active_period(code)
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
                await uow.devices.add_period(new_period)

            elif active_period.status_code != new_status_int:
                # Case 2: Status changed -> Close old period, open new one

                # IMMUTABLE PATTERN: with_end_time() returns a NEW StatusPeriod
                # instead of mutating the existing one
                closed_period = active_period.with_end_time(timestamp)
                await uow.devices.update_period(closed_period)

                # Create new period with new status
                new_period = StatusPeriod.create(
                    id=str(uuid4()),
                    code=code,
                    raw_status=new_status,
                    start=timestamp,
                    end=None,
                )
                await uow.devices.add_period(new_period)

                logger.debug(f"Status Changed [{code}]: " f"{active_period.status_name} -> {new_status}")

            # Case 3: Status unchanged -> Period continues, do nothing

        except Exception as e:
            logger.debug(f"Status history handling skipped for {code}: {e}")

    @staticmethod
    def _parse_status_code(raw_status: str | int) -> int:
        """Parse raw status to integer for comparison."""
        if isinstance(raw_status, int):
            return raw_status
        try:
            return int(raw_status)
        except (ValueError, TypeError):
            return 0
