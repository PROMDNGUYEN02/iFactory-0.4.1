"""
Sync Devices Use Cases.
Handles synchronization logic for single and multiple devices.
"""

import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any, Union

from iFactory.application.ports.uow import AbstractUnitOfWork
from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.domain.entities.device import Device
from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)


# ... (Giữ nguyên hàm _update_history_logic cho Realtime Sync) ...
async def _update_history_logic(
    history_repo,
    code: EquipmentCode,
    new_status: MachineStatus,
    timestamp: datetime,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    equip_name: Optional[str] = None,
) -> None:
    latest_period: Optional[StatusPeriod] = await history_repo.get_latest_status(code)
    effective_start = start_time if start_time else timestamp

    if not latest_period:
        actual_end = end_time
        if actual_end and actual_end < effective_start:
            actual_end = effective_start
        new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange(start=effective_start, end=actual_end))
        await history_repo.save_status_period(new_period, equip_name=equip_name)
        return

    if latest_period.status != new_status:
        closing_time = effective_start
        if closing_time < latest_period.time_range.start:
            closing_time = latest_period.time_range.start
        closed_period = latest_period.with_end_time(closing_time)
        await history_repo.save_status_period(closed_period, equip_name=equip_name)
        new_period_start = max(effective_start, closing_time)
        actual_end = end_time
        if actual_end and actual_end < new_period_start:
            actual_end = new_period_start
        new_period = StatusPeriod(equipment_code=code, status=new_status, time_range=TimeRange(start=new_period_start, end=actual_end))
        await history_repo.save_status_period(new_period, equip_name=equip_name)

    elif end_time and latest_period.time_range.end is None:
        closing_time = end_time
        if closing_time < latest_period.time_range.start:
            closing_time = latest_period.time_range.start
        closed_period = latest_period.with_end_time(closing_time)
        await history_repo.save_status_period(closed_period, equip_name=equip_name)


class SyncAllDevicesCommand:
    # ... (Giữ nguyên Class này cho Dashboard/Realtime) ...
    def __init__(
        self,
        remote_source: IRemoteDataSource,
        dual_uow_factory: Callable[[], AbstractUnitOfWork],
    ):
        self._remote_source = remote_source
        self._uow_factory = dual_uow_factory

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        try:
            remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        except Exception as e:
            logger.error(f"Failed to fetch from remote source: {e}")
            return 0

        if not remote_records:
            return 0

        count = 0
        async with self._uow_factory() as uow:
            for record in remote_records:
                try:
                    await self._process_record(uow, record)
                    count += 1
                except Exception as e:
                    code = record.get("equip_code", "unknown")
                    logger.warning(f"Error syncing device {code}: {e}")

            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Synchronized {count} devices.")
        return count

    async def _process_record(self, uow: AbstractUnitOfWork, record: Dict[str, Any]) -> None:
        raw_code = str(record.get("equip_code"))
        raw_status = record.get("raw_status", "0")
        timestamp = record.get("last_update") or datetime.now()
        reason_code = record.get("reason_code")
        equip_name = record.get("equip_name")
        remote_start_time = record.get("start_time")
        remote_end_time = record.get("end_time")

        code_vo = EquipmentCode(raw_code)
        try:
            status_enum = MachineStatus(int(raw_status))
        except (ValueError, TypeError):
            status_enum = MachineStatus.UNKNOWN

        device = Device(
            equipment_code=code_vo,
            current_status=status_enum,
            last_updated_at=timestamp,
            equip_name=equip_name,
            reason_code=reason_code,
        )
        await uow.devices.save(device)

        if uow.history:
            await _update_history_logic(
                uow.history,
                code_vo,
                status_enum,
                timestamp,
                remote_start_time,
                remote_end_time,
                equip_name=equip_name,
            )


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs History for a specific device.
    OPTIMIZED: Bulk processing and Data filling.
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str, days: int = 30) -> bool:
        try:
            # 1. Fetch toàn bộ dữ liệu (Raw)
            data = await self._remote_api.fetch_device_status(equip_code, days=days)
            if not data:
                return False

            records = data if isinstance(data, list) else [data]
            if not records:
                return True

            # 2. Tìm 'equip_name' chuẩn nhất (Lấy từ bản ghi đầu tiên có dữ liệu)
            master_equip_name = None
            for r in records:
                if r.get("equip_name"):
                    master_equip_name = r.get("equip_name")
                    break

            # (Fallback: Nếu không thấy trong data, có thể query DB local, nhưng tạm thời để None)

            # Chuẩn bị danh sách Batch
            batch_periods: List[StatusPeriod] = []
            latest_record = None
            latest_timestamp = datetime.min

            async with self._uow as uow:
                for record in records:
                    raw_status = record.get("equip_status", "0")
                    # Sử dụng timestamp để tìm bản ghi mới nhất cho bảng Devices
                    timestamp = record.get("last_update") or datetime.now()

                    # Logic tìm bản ghi mới nhất (để update Hot Store 1 lần)
                    if timestamp >= latest_timestamp:
                        latest_timestamp = timestamp
                        latest_record = record

                    # Logic History
                    start_time = record.get("start_time")
                    if start_time:
                        code_vo = EquipmentCode(record.get("equip_code"))
                        end_time = record.get("end_time")

                        try:
                            status_enum = MachineStatus(int(raw_status))
                        except (ValueError, TypeError):
                            status_enum = MachineStatus.UNKNOWN

                        # Fix Time Travel & Prepare Object
                        actual_end = end_time if end_time else None
                        if actual_end and actual_end < start_time:
                            actual_end = start_time

                        # Tạo Period Object và thêm vào list (Chưa lưu DB)
                        period = StatusPeriod(equipment_code=code_vo, status=status_enum, time_range=TimeRange(start=start_time, end=actual_end))
                        batch_periods.append(period)

                # 3. BULK SAVE HISTORY (Ghi 1 lần duy nhất)
                # Truyền master_equip_name để điền vào tất cả các dòng (kể cả dòng bị null)
                if uow.history and batch_periods:
                    await uow.history.bulk_save_status_history(batch_periods, equip_name=master_equip_name)

                # 4. UPDATE HOT STORE (Chỉ 1 lần duy nhất)
                if latest_record:
                    raw_status = latest_record.get("equip_status", "0")
                    try:
                        status_enum = MachineStatus(int(raw_status))
                    except:
                        status_enum = MachineStatus.UNKNOWN

                    device = Device(
                        equipment_code=EquipmentCode(latest_record.get("equip_code")),
                        current_status=status_enum,
                        last_updated_at=latest_timestamp,
                        equip_name=master_equip_name,  # Luôn dùng tên chuẩn
                        reason_code=latest_record.get("reason_code"),
                    )
                    await uow.devices.save(device)

                await uow.commit()

            logger.info(f"Synced {len(batch_periods)} history records for {equip_code} (Name: {master_equip_name})")
            return True

        except Exception as e:
            logger.error(f"Failed to sync device {equip_code}: {e}")
            return False
