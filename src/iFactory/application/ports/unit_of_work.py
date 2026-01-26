from abc import ABC, abstractmethod
from iFactory.application.ports.repository import IDeviceRepository


class IUnitOfWork(ABC):
    """
    Port for managing transaction boundaries.
    """

    # Repositories accessible within the transaction
    devices: IDeviceRepository

    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork":
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    async def commit(self) -> None:
        pass

    @abstractmethod
    async def rollback(self) -> None:
        pass
