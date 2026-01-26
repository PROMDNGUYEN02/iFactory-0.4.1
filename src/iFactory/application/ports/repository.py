from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional
from iFactory.domain.entities.device import Device

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
    async def get_by_equipment_code(self, equip_code: str) -> Optional[Device]:
        pass

    @abstractmethod
    async def save_many(self, devices: List[Device]) -> int:
        pass

    @abstractmethod
    async def get_history(self, equip_code: str) -> List[Device]:
        pass
