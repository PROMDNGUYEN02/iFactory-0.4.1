"""
Device Repository Interface - Contract for device persistence.

This interface defines how application accesses Device aggregate roots.
Infrastructure layer implements this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence, TYPE_CHECKING

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode

if TYPE_CHECKING:
    from ..value_objects.status import Status

__all__ = ["DeviceRepository"]


class DeviceRepository(ABC):
    """
    Abstract Repository for Device Aggregate Root.

    Contract:
        - Mọi method đều async (để non-blocking cho Qt GUI)
        - Input/Output dùng Value Objects (type-safe)
        - Return Entity hoặc None (không DTO, không ORM)

    Implementation:
        - Infrastructure layer implement interface này
        - Use Cases chỉ interface, không concrete type
    """

    # ====== QUERIES ======

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """
        Lấy device theo equipment code.

        Args:
            code: Equipment Code value object

        Returns:
            Device entity hoặc None nếu không tìm thấy
        """
        pass

    @abstractmethod
    async def get_by_codes(
        self,
        codes: Sequence[str]
    ) -> Sequence[Device]:
        """
        Lấy nhiều devices theo equipment codes.

        Args:
            codes: List của equipment code strings

        Returns:
            Sequence của Device entities (có thể rỗng)
        """
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """
        Lấy tất cả devices.

        Returns:
            Sequence của tất cả Device entities
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: "Status"
    ) -> Sequence[Device]:
        """
        Lấy devices có status cụ thể.

        Args:
            status: Status Value Object or status code string

        Returns:
            Sequence của Device entities có status đó
        """
        pass

    @abstractmethod
    async def get_by_status_codes(self, codes: Sequence[str]) -> Sequence[Device]:
        """
        Lấy devices có các status codes cụ thể.

        Args:
            codes: List của status codes (e.g., ["1", "3"])

        Returns:
            Sequence của Device entities có status codes đó
        """
        pass

    @abstractmethod
    async def get_requiring_attention(self) -> Sequence[Device]:
        """
        Lấy devices cần sự chú ý (alarm, stop).

        Returns:
            Sequence của Device entities cần attention
        """
        pass

    @abstractmethod
    async def get_running_devices(self) -> Sequence[Device]:
        """
        Lấy devices đang chạy.

        Returns:
            Sequence của Device entities đang running
        """
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        """
        Kiểm tra device có tồn tại không.

        Args:
            code: Equipment Code muốn kiểm tra

        Returns:
            True nếu tồn tại, False nếu không
        """
        pass

    @abstractmethod
    async def count(self) -> int:
        """
        Đếm tổng số devices.

        Returns:
            Tổng số devices
        """
        pass

    # ====== COMMANDS ======

    @abstractmethod
    async def save(self, device: Device) -> None:
        """
        Lưu hoặc update device (Upsert).

        Args:
            device: Device Aggregate Root entity

        Raises:
            RepositoryError: Nếu lưu thất bại
        """
        pass

    @abstractmethod
    async def save_many(self, devices: Sequence[Device]) -> int:
        """
        Lưu nhiều devices (batch).

        Args:
            devices: Sequence của Device entities

        Returns:
            Số lượng devices đã lưu

        Raises:
            RepositoryError: Nếu lưu thất bại
        """
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        """
        Xóa device.

        Args:
            code: Equipment Code của device muốn xóa

        Returns:
            True nếu xóa thành công, False nếu không tìm thấy

        Raises:
            RepositoryError: Nếu xóa thất bại
        """
        pass

    @abstractmethod
    async def delete_all(self) -> int:
        """
        Xóa tất cả devices.

        Returns:
            Số lượng devices đã xóa

        Raises:
            RepositoryError: Nếu xóa thất bại
        """
        pass
