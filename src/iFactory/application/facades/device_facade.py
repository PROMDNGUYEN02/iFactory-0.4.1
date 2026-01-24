"""
Device Facade - Entry point for Presentation layer.

Orchestrates Device Use Cases and provides clean, simple API for UI.
Ensures Presentation only calls Application layer.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Dict, Optional, Sequence

if TYPE_CHECKING:
    from ...domain.entities import Device
    from ...domain.repositories import DeviceRepository

from ..use_cases.device.get_all_devices_status import GetAllDevicesStatusUseCase
from ..use_cases.device.get_latest_status import GetLatestDeviceStatusUseCase
from ..use_cases.device.get_device_history import GetDeviceHistoryUseCase
from ..view_models.device_view_model import DeviceViewModel
from ..services.status_ui_mapper import StatusUIMapper

__all__ = ["DeviceFacade"]

logger = logging.getLogger(__name__)


class DeviceFacade:
    """
    Facade for Device operations.

    Trách nhiệm:
        - Orchestrate Device Use Cases
        - Provide simple, UI-friendly API methods
        - Handle error translation for Presentation
        - Map results to View Models

    Quy ước:
        - Presentation layer chỉ gọi DeviceFacade
        - Presentation KHÔNG biết về Use Cases hoặc Repositories
        - Facade quản lý dependency injection internally
    """

    __slots__ = (
        "_get_all_uc",
        "_get_latest_uc",
        "_get_history_uc",
        "_theme",
    )

    def __init__(
        self,
        get_all_use_case: GetAllDevicesStatusUseCase,
        get_latest_use_case: GetLatestDeviceStatusUseCase,
        get_history_use_case: GetDeviceHistoryUseCase,
        default_theme: str = "light",
    ):
        """
        Initialize facade with required Use Cases.

        Args:
            get_all_use_case: Use case for getting all devices
            get_latest_use_case: Use case for getting single device
            get_history_use_case: Use case for getting device history
            default_theme: Default UI theme ('light' or 'dark')
        """
        self._get_all_uc = get_all_use_case
        self._get_latest_uc = get_latest_use_case
        self._get_history_uc = get_history_use_case
        self._theme = default_theme

    def set_theme(self, theme: str) -> None:
        """
        Update current UI theme.

        Args:
            theme: 'light' or 'dark'
        """
        self._theme = "dark" if theme == "dark" else "light"
        logger.debug(f"[DeviceFacade] Theme set to: {self._theme}")

    # ====== QUERY METHODS ======

    async def get_all_devices(self, equipment_codes: Optional[Sequence[str]] = None) -> Dict[str, DeviceViewModel]:
        """
        Get all devices (or filtered) as View Models.

        Args:
            equipment_codes: Optional list of equipment codes to filter

        Returns:
            Dictionary mapping equipment code → DeviceViewModel

        Raises:
            RepositoryError: If data access fails
        """
        try:
            dtos = await self._get_all_uc.execute(equipment_codes or [])

            result = {}
            for code, dto in dtos.items():
                result[code] = DeviceViewModel.from_domain_data(
                    equipment_code=dto.equip_code,
                    status_code=dto.status_code,
                    status_name=dto.status_name,
                    theme=self._theme,
                    last_update=dto.last_update.isoformat() if dto.last_update else None,
                )

            logger.info(f"[DeviceFacade] Retrieved {len(result)} devices")
            return result

        except Exception as e:
            logger.error(f"[DeviceFacade] Failed to get all devices: {e}", exc_info=True)
            return {}

    async def get_device(self, equipment_code: str) -> Optional[DeviceViewModel]:
        """
        Get single device as View Model.

        Args:
            equipment_code: Equipment code to retrieve

        Returns:
            DeviceViewModel or None if not found
        """
        try:
            dto = await self._get_latest_uc.execute(equipment_code)

            if dto is None:
                return None

            return DeviceViewModel.from_domain_data(
                equipment_code=dto.equip_code,
                status_code=dto.status_code,
                status_name=dto.status_name,
                theme=self._theme,
                last_update=dto.last_update.isoformat() if dto.last_update else None,
            )

        except Exception as e:
            logger.error(f"[DeviceFacade] Failed to get device {equipment_code}: {e}", exc_info=True)
            return None

    async def get_multiple_devices(
        self,
        equipment_codes: Sequence[str],
    ) -> Dict[str, DeviceViewModel]:
        """
        Get multiple devices as View Models.

        Args:
            equipment_codes: List of equipment codes to retrieve

        Returns:
            Dictionary mapping equipment code → DeviceViewModel
        """
        return await self.get_all_devices(equipment_codes)

    # ====== STATUS SUMMARY ======

    def get_status_display(self, status_code: str) -> str:
        """
        Get display text for a status code.

        Convenience method for UI without needing to import StatusUIMapper.

        Args:
            status_code: Database status code

        Returns:
            Display text (e.g., 'RUNNING')
        """
        return StatusUIMapper.get_display_text(status_code)

    def get_status_color(self, status_code: str) -> str:
        """
        Get color for a status code with current theme.

        Convenience method for UI.

        Args:
            status_code: Database status code

        Returns:
            Hex color string
        """
        return StatusUIMapper.get_color(status_code, self._theme)

    def get_status_emoji(self, status_code: str) -> str:
        """
        Get emoji for a status code.

        Convenience method for UI.

        Args:
            status_code: Database status code

        Returns:
            Emoji unicode character
        """
        return StatusUIMapper.get_emoji(status_code)

    def get_all_status_ui_data(self) -> Dict[str, Dict[str, str]]:
        """
        Get all status UI data.

        For use by UI theme selection, status legend, etc.

        Returns:
            Dictionary mapping status code to UI data dict
        """
        return StatusUIMapper.get_all_ui_data()

    # ====== UTILITY METHODS ======

    def is_running(self, status_code: str) -> bool:
        """Check if status represents running state."""
        return StatusUIMapper.is_running(status_code)

    def requires_attention(self, status_code: str) -> bool:
        """Check if status requires operator attention."""
        return StatusUIMapper.requires_attention(status_code)
