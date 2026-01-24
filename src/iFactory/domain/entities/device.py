"""
Device Entity - Aggregate Root for device management.

Business Rules:
    - Equipment code is the unique identifier
    - Status updates emit domain events
    - Status is managed via Status Value Object
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from ..enums.device_status import DeviceStatus
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status

if TYPE_CHECKING:
    from ..events.device_status_changed import StatusChangedEvent

__all__ = ["Device"]


@dataclass(slots=True)
class Device:
    """
    Device Aggregate Root.

    Trách nhiệm:
        - Quản lý trạng thái thiết bị
        - Emit domain events khi trạng thái thay đổi
        - Enforce business rules về status transitions

    Invariants:
        - equipment_code luôn valid (EquipmentCode đảm bảo điều này)
        - current_status luôn là Status Value Object
        - last_update không null sau lần update đầu tiên

    Business Rules:
        - Status updates chỉ thực hiện khi có thay đổi thực sự
        - Domain events được emit khi status thay đổi
    """

    equipment_code: EquipmentCode
    current_status: Status = field(default_factory=Status.unknown)
    last_update: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

    _events: List["StatusChangedEvent"] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        """
        Validate sau khi khởi tạo.

        Defensive programming: nếu truyền string thô,
        tự động chuyển thành EquipmentCode/Status.
        """
        if not isinstance(self.equipment_code, EquipmentCode):
            object.__setattr__(
                self, 
                "equipment_code", 
                EquipmentCode(self.equipment_code)
            )

        if not isinstance(self.current_status, Status):
            object.__setattr__(
                self, 
                "current_status", 
                Status(DeviceStatus.from_code_or_name(self.current_status))
            )

    @classmethod
    def create(
        cls,
        code: str | EquipmentCode,
        status: str | DeviceStatus | Status,
        last_update: datetime | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> "Device":
        """
        Factory method tạo Device an toàn.

        Args:
            code: Mã thiết bị (string hoặc EquipmentCode)
            status: Trạng thái (string, enum hoặc Status VO)
            last_update: Timestamp lần cập nhật
            name: Tên thiết bị (optional)
            description: Mô tả (optional)

        Returns:
            Device entity đã validated
        """
        if isinstance(code, EquipmentCode):
            ec = code
        else:
            ec = EquipmentCode(code)

        if isinstance(status, Status):
            s = status
        elif isinstance(status, DeviceStatus):
            s = Status(status)
        else:
            s = Status(DeviceStatus.from_code_or_name(status))

        return cls(
            equipment_code=ec,
            current_status=s,
            last_update=last_update,
            name=name,
            description=description,
        )

    # ====== BUSINESS BEHAVIOR ======

    def update_status(
        self, 
        new_status: Status | DeviceStatus | str,
        update_time: datetime | None = None
    ) -> bool:
        """
        Business Rule: Cập nhật trạng thái.

        Chỉ cập nhật nếu trạng thái thay đổi thực sự.
        Emit domain event khi có thay đổi.

        Args:
            new_status: Trạng thái mới
            update_time: Timestamp cập nhật (nếu None → now)

        Returns:
            True nếu status thay đổi, False nếu không đổi
        """
        # Normalize input
        if isinstance(new_status, str):
            new_status = Status(DeviceStatus.from_code_or_name(new_status))
        elif isinstance(new_status, DeviceStatus):
            new_status = Status(new_status)

        # Business Rule: Không update nếu không thay đổi
        if self.current_status == new_status:
            return False

        # Emit domain event
        from ..events.device_status_changed import StatusChangedEvent

        event = StatusChangedEvent(
            equipment_code=self.code,
            previous_status=self.current_status,
            new_status=new_status,
            changed_at=update_time or datetime.now(),
        )
        self._events.append(event)

        # Cập nhật state
        object.__setattr__(self, "current_status", new_status)
        object.__setattr__(
            self, 
            "last_update", 
            update_time or datetime.now()
        )
        return True

    def can_transition_to(
        self, 
        new_status: Status | DeviceStatus
    ) -> bool:
        """
        Business Rule: Kiểm tra transition có hợp lệ không.

        Future: Có thể thêm constraints phức tạp hơn
        (ví dụ: không thể từ ALARM → RUNNING trực tiếp).

        Args:
            new_status: Trạng thái muốn chuyển tới

        Returns:
            True nếu transition được phép
        """
        # Hiện tại: tất cả transitions đều hợp lệ
        # Future: Add transition rules
        return True

    # ====== EVENT HANDLING ======

    def get_events(self) -> List["StatusChangedEvent"]:
        """
        Lấy và xóa các event đã phát sinh.

        Returns:
            List of events (sau đó events list được clear)
        """
        from ..events.device_status_changed import StatusChangedEvent

        events = self._events.copy()
        self._events.clear()
        return events

    def has_uncommitted_events(self) -> bool:
        """Check nếu có event chưa commit."""
        return len(self._events) > 0

    # ====== PROPERTY ACCESSORS ======

    @property
    def code(self) -> str:
        """Get string value của equipment code."""
        return self.equipment_code.value

    @property
    def status_code(self) -> str:
        """Get status code string."""
        return self.current_status.code

    @property
    def status_name(self) -> str:
        """Get status name (snake_case)."""
        return self.current_status.name

    @property
    def is_running(self) -> bool:
        """Check nếu đang chạy."""
        return self.current_status.is_running

    @property
    def requires_attention(self) -> bool:
        """Check nếu cần sự chú ý."""
        return self.current_status.requires_attention

    # ====== COMPARISON ======

    def __eq__(self, other: object) -> bool:
        """So sánh theo equipment_code."""
        if not isinstance(other, Device):
            return False
        return self.equipment_code == other.equipment_code

    def __hash__(self) -> int:
        """Hash theo equipment_code."""
        return hash(self.equipment_code)

    def __str__(self) -> str:
        """String representation."""
        name_part = f" - {self.name}" if self.name else ""
        return f"Device({self.code}{name_part} - {self.status_name})"

    def __repr__(self) -> str:
        """Debug representation."""
        return f"Device(code={self.code!r}, status={self.status_name!r}, last_update={self.last_update!r})"
