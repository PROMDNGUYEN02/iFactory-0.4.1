from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional
from datetime import datetime
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T, ID]):
    @abstractmethod
    async def get_by_id(self, id: ID) -> Optional[T]:
        pass

    @abstractmethod
    async def save(self, entity: T) -> None:
        pass

    @abstractmethod
    async def delete(self, entity: T) -> None:
        pass


class IDeviceRepository(IRepository[Device, str]):
    @abstractmethod
    async def get_all(self) -> List[Device]:
        pass

    @abstractmethod
    async def get_by_code(self, equip_code: str) -> Optional[Device]:
        pass

    @abstractmethod
    async def save_many(self, devices: List[Device]) -> int:
        pass

    # --- Time Series / History Methods ---
    @abstractmethod
    async def get_history(self, equip_code: str, start: datetime, end: datetime) -> List[StatusPeriod]:
        """Lấy lịch sử trạng thái trong khoảng thời gian."""
        pass

    @abstractmethod
    async def get_active_period(self, equip_code: str) -> Optional[StatusPeriod]:
        """Lấy kỳ trạng thái đang mở (chưa có end_time)."""
        pass

    @abstractmethod
    async def add_period(self, period: StatusPeriod) -> None:
        """Thêm kỳ trạng thái mới."""
        pass

    @abstractmethod
    async def update_period(self, period: StatusPeriod) -> None:
        """Cập nhật kỳ trạng thái (thường dùng để đóng end_time)."""
        pass
