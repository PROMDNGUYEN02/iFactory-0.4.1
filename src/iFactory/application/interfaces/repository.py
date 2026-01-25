from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T, ID]):
    @abstractmethod
    def get_by_id(self, id: ID) -> Optional[T]:
        pass

    @abstractmethod
    def save(self, entity: T) -> None:
        pass

    @abstractmethod
    def delete(self, entity: T) -> None:
        pass
