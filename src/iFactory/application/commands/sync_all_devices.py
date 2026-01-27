import logging
from typing import List, Optional
from datetime import datetime
import uuid

from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Đồng bộ dữ liệu và TỰ ĐỘNG TẠO LỊCH SỬ CHO GANTT CHART.
    Sử dụng Domain logic để đảm bảo tính toàn vẹn dữ liệu.
    """

    def __init__(self, remote_source: IRemoteDataSource, uow: AbstractUnitOfWork):
        self._remote_source = remote_source
        self._uow = uow

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        # 1. Lấy dữ liệu từ nguồn MSSQL
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

                    # 2. Cập nhật trạng thái tức thời (Snapshot)
                    # Device.create sẽ validate EquipmentCode và MachineStatus
                    device_entity = Device.create(code=code, raw_status=new_status, last_update=timestamp)
                    await uow.devices.save(device_entity)

                    # 3. LOGIC THEO DÕI LỊCH SỬ (Dành cho Gantt Chart)
                    active_period = await uow.devices.get_active_period(code)

                    if not active_period:
                        # Case 1: Chưa có kỳ nào -> Tạo kỳ khởi đầu
                        # [FIXED] Gọi đúng tham số 'code' thay vì 'device_code'
                        new_period = StatusPeriod.create(id=str(uuid.uuid4()), code=code, raw_status=new_status, start=timestamp, end=None)
                        await uow.devices.add_period(new_period)

                    elif active_period.status_code != new_status:
                        # Case 2: Trạng thái thay đổi -> Kết thúc kỳ cũ, mở kỳ mới

                        # Cập nhật end_time cho kỳ hiện tại thông qua setter
                        # [FIXED] Đảm bảo logic setter trong StatusPeriod xử lý TimeRange mới an toàn
                        active_period.end_time = timestamp
                        await uow.devices.update_period(active_period)

                        # Tạo kỳ mới với trạng thái mới
                        new_period = StatusPeriod.create(id=str(uuid.uuid4()), code=code, raw_status=new_status, start=timestamp, end=None)
                        await uow.devices.add_period(new_period)
                        logger.info(f"Status Changed [{code}]: {active_period.status_code} -> {new_status}")

                    count += 1
                except Exception as e:
                    # Log cảnh báo chi tiết từng máy để không làm gián đoạn cả tiến trình
                    logger.warning(f"Error processing record for {record.get('equip_code', 'unknown')}: {e}")

            # Lưu toàn bộ thay đổi vào database cục bộ sau khi xử lý xong list
            await uow.commit()

        if count > 0:
            logger.info(f"[Sync] Successfully synchronized {count} devices.")
        return count
