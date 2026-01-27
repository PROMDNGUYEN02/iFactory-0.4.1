import logging
from datetime import datetime
from typing import List, Optional

from iFactory.application.ports.remote_data_source import IRemoteDataSource
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.exceptions.application_exceptions import SyncError
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


class SyncDevicesCommand:
    """
    Orchestrates the synchronization of device status from remote sources.
    Handles Domain Event side-effects (creating history periods).
    """

    def __init__(
        self,
        uow: AbstractUnitOfWork,
        remote_source: IRemoteDataSource,
    ):
        self._uow = uow
        self._remote_source = remote_source

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> None:
        """
        Syncs all devices or a specific list.
        """
        try:
            raw_data = await self._remote_source.fetch_latest_status(equipment_codes)
            if not raw_data:
                logger.info("No data received from remote source.")
                return

            async with self._uow as uow:
                for record in raw_data:
                    await self._process_record(uow, record)

                await uow.commit()
                logger.info(f"Successfully synced {len(raw_data)} devices.")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise SyncError(f"Synchronization workflow failed: {str(e)}") from e

    async def _process_record(self, uow: AbstractUnitOfWork, record: dict) -> None:
        code_str = record.get("equip_code")
        status_val = record.get("raw_status")
        timestamp = record.get("timestamp", datetime.now())

        if not code_str or status_val is None:
            return

        # 1. Parse Domain Types
        try:
            equip_code = EquipmentCode(code_str)
            new_status = MachineStatus(int(status_val))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid data for device {code_str}: {e}")
            return

        # 2. Reconstitute Aggregate
        device = await uow.devices.get_by_code(equip_code)
        if not device:
            device = Device.register_new(code=equip_code)
            logger.info(f"Registered new device: {equip_code}")

        # 3. Execute Domain Logic
        device.update_status(new_status, timestamp)

        # 4. Handle Side Effects (Domain Events)
        # In a lite architecture, we handle events explicitly here within the transaction.
        # Ideally, an EventDispatcher would handle this, but explicit is fine for lite.
        for event in device.collect_events():
            if event.event_type == "StatusChangedEvent":
                # Close previous period (if any) and start new one
                # Note: This logic assumes the repository or domain policy helps match periods.
                # Here we create the 'new' period starting at event time.

                # Close the 'latest' open period in history
                last_period = await uow.production.get_latest_status(equip_code)
                if last_period and last_period.time_range.is_ongoing:
                    # Logic to close: create a closed version
                    closed_period = last_period.with_end_time(event.occurred_at)
                    await uow.production.save_status_period(closed_period)

                # Create new open period
                new_period = StatusPeriod(equipment_code=equip_code, status=event.new_status, time_range=TimeRange.starting_from(event.occurred_at))
                await uow.production.save_status_period(new_period)

        # 5. Persist Aggregate
        await uow.devices.save(device)
