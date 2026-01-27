"""
Application Port: Unit of Work Interface.
Định nghĩa Interface quản lý Transaction bất đồng bộ (Async) cho tầng Infrastructure.
"""

from __future__ import annotations
import abc
from typing import TYPE_CHECKING

# Tránh lỗi vòng lặp import (Circular Import) bằng TYPE_CHECKING
if TYPE_CHECKING:
    from iFactory.application.ports.repository import IDeviceRepository


class AbstractUnitOfWork(abc.ABC):
    """
    Port for managing transaction boundaries (Async Context Manager).
    Đảm bảo tính toàn vẹn của dữ liệu (ACID) cho các thao tác với Database.
    """

    # Repositories accessible within the transaction
    devices: IDeviceRepository

    @abc.abstractmethod
    async def __aenter__(self) -> AbstractUnitOfWork:
        """Kích hoạt Async Context Manager"""
        pass

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Xử lý đóng/rollback khi thoát khỏi khối with"""
        pass

    @abc.abstractmethod
    async def commit(self) -> None:
        """Lưu các thay đổi vào Database."""
        pass

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Hoàn tác các thay đổi nếu có lỗi."""
        pass
