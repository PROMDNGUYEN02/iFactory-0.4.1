from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .base import AggregateRoot
from ..value_objects.equipment_code import EquipmentCode
from ..enums.machine_status import MachineStatus
from ..events.device_events import StatusChangedEvent
from ..policies.status_transition_policy import StatusTransitionPolicy


@dataclass(slots=True)
class Device(AggregateRoot):
    """
    Aggregate Root đại diện cho một thiết bị sản xuất.
    Đảm bảo các ràng buộc nghiệp vụ về chuyển đổi trạng thái (state transitions).
    """

    equipment_code: EquipmentCode
    current_status: MachineStatus = field(default=MachineStatus.UNKNOWN)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def create(cls, code: str, raw_status: str, last_update: Optional[datetime] = None) -> Device:
        """
        [FIXED] Factory method dùng để tái tạo (reconstruct) Entity từ dữ liệu hạ tầng (MSSQL/SQLite).
        Giúp SyncCommand có thể khởi tạo đối tượng Device mà không cần biết logic map Enum.
        """
        # Ánh xạ từ raw_status (chuỗi từ MSSQL) sang Enum MachineStatus
        # Sử dụng from_business_term hoặc khởi tạo trực tiếp tùy theo Enum của bạn
        try:
            status = MachineStatus.from_business_term(raw_status)
        except (ValueError, AttributeError):
            # Fallback nếu không map được
            try:
                status = MachineStatus(int(raw_status))
            except:
                status = MachineStatus.UNKNOWN

        return cls(equipment_code=EquipmentCode(code), current_status=status, last_update=last_update or datetime.now())

    @classmethod
    def register_new(cls, code: str, name: Optional[str] = None) -> Device:
        """Factory method để đăng ký mới một thiết bị vào hệ thống."""
        return cls(equipment_code=EquipmentCode(code), name=name, current_status=MachineStatus.UNKNOWN, last_update=datetime.now())

    @property
    def is_operational(self) -> bool:
        """Kiểm tra máy có đang trong trạng thái sản xuất hay không."""
        # Giả định is_running được định nghĩa trong MachineStatus enum
        return getattr(self.current_status, "is_running", False)

    # --- Các phương thức nghiệp vụ (Domain Behaviors) ---

    def start_production(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.RUNNING, timestamp)

    def trigger_alarm(self, timestamp: datetime) -> None:
        self._transition_to(MachineStatus.ALARM, timestamp)

    def report_sensor_status(self, raw_status: str, timestamp: datetime) -> None:
        """Telemetry update từ phần cứng vật lý."""
        new_status = MachineStatus.from_business_term(raw_status)
        self._transition_to(new_status, timestamp)

    def _transition_to(self, new_status: MachineStatus, timestamp: datetime) -> None:
        """Thực thi thay đổi trạng thái và áp dụng Policy kiểm tra."""
        if self.current_status == new_status:
            return

        # Kiểm tra tính hợp lệ của việc chuyển đổi (Ví dụ: Đang Alarm không thể nhảy thẳng sang Running)
        StatusTransitionPolicy.validate(self.current_status, new_status)

        # Ghi nhận Domain Event
        event = StatusChangedEvent(
            occurred_at=timestamp, equipment_code=self.equipment_code.value, previous_status=self.current_status, new_status=new_status
        )
        self._record_event(event)

        # Cập nhật trạng thái
        self.current_status = new_status
        self.last_update = timestamp

    # Helper properties cho Repository/Mapper
    @property
    def code(self) -> str:
        return self.equipment_code.value

    @property
    def status(self) -> int:
        return self.current_status.value
