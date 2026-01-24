"""
Device Presenter - Formats device data for UI display.

Clean Architecture Compliant:
- NO imports from Domain layer
- NO imports from Infrastructure layer
- Only imports from Application layer
- Only UI formatting logic (no business rules)
- Uses DeviceFacade for all data access
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Any

if TYPE_CHECKING:
    from ...application.facades import DeviceFacade
    from ...application.view_models import DeviceViewModel

logger = logging.getLogger(__name__)


class DevicePresenter:
    """
    Presenter for device data.

    Trách nhiệm:
        - Format Application View Models for UI display
        - Handle legacy data formats (backward compatibility)
        - Provide UI-specific formatting (timestamps, etc.)

    Clean Architecture Rules:
        - ✅ KHÔNG import từ Domain layer
        - ✅ KHÔNG import từ Infrastructure layer
        - ✅ CHỈ import từ Application layer (DeviceFacade, DeviceViewModel)
        - ✅ KHÔNG chứa business logic
        - ✅ CHỈ formatting logic
    """

    __slots__ = ("_theme",)

    def __init__(self, theme: str = "light"):
        """
        Initialize presenter.

        Args:
            theme: Initial theme mode ('light' or 'dark')
        """
        self._theme = "dark" if theme == "dark" else "light"
        logger.debug(f"[DevicePresenter] Initialized with theme: {self._theme}")

    def set_theme(self, theme: str) -> None:
        """
        Set theme mode.

        Args:
            theme: 'light' or 'dark'
        """
        self._theme = "dark" if theme == "dark" else "light"
        logger.debug(f"[DevicePresenter] Theme updated: {self._theme}")

    # ====== PUBLIC API FOR UI ======

    def format_for_update(
        self,
        statuses: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Format raw status data for UI update (device refresh).

        This is used by DeviceController.refresh_all_devices() to convert
        DeviceStatusDTO or dict data into UI-ready format.

        Args:
            statuses: Dictionary of device statuses (DeviceStatusDTO or dict)

        Returns:
            Dictionary suitable for Qt widgets and managers
        """
        result = {}
        for code, data in statuses.items():
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            elif not isinstance(data, dict):
                logger.warning(f"[DevicePresenter] Unexpected type for {code}: {type(data)}")
                continue

            result[code] = {
                "device_id": data.get("equip_code", code),
                "display_name": data.get("display_name", code),
                "status_code": str(data.get("status_code", "0")),
                "status_display": data.get("status_display", "UNKNOWN"),
                "status_emoji": data.get("status_emoji", ""),
                "status_color": data.get("status_color", "#808080"),
                "status_category": data.get("status_category", "unknown"),
                "is_running": data.get("is_running", False),
                "requires_attention": data.get("requires_attention", False),
                "last_update": data.get("last_update"),
                # Legacy field names (backward compatibility)
                "equip_code": data.get("equip_code", code),
                "equipment_code": data.get("equip_code", code),
                "name": data.get("display_name", code),
                "status": str(data.get("status_code", "0")),
                "color": data.get("status_color", "#808080"),
            }
        logger.debug(f"[DevicePresenter] Formatted {len(result)} devices for update")
        return result

    def present_device_list(
        self,
        statuses: Dict[str, Any],
    ) -> Dict[str, DeviceViewModel]:
        """
        Present list of device statuses for UI.

        This method is called by UIContainer during refresh.

        Args:
            statuses: Dictionary of device statuses (DeviceStatusDTO or dict)

        Returns:
            Dictionary mapping equipment code → DeviceViewModel
        """
        from iFactory.application.view_models import DeviceViewModel

        result = {}
        for code, data in statuses.items():
            try:
                if hasattr(data, "equip_code"):
                    result[code] = DeviceViewModel(
                        device_id=data.equip_code,
                        display_name=data.equip_code,
                        status_code=str(data.status_code),
                        status_display=data.status_display,
                        status_emoji="",
                        status_color=data.status_color,
                        status_category="unknown",
                        is_running=False,
                        requires_attention=False,
                        last_update=data.last_update.isoformat() if data.last_update else None,
                    )
                elif isinstance(data, dict):
                    result[code] = DeviceViewModel(
                        device_id=data.get("equip_code", code),
                        display_name=data.get("equip_code", code),
                        status_code=str(data.get("status_code", "0")),
                        status_display=data.get("status_display", "UNKNOWN"),
                        status_emoji=data.get("status_emoji", ""),
                        status_color=data.get("status_color", "#808080"),
                        status_category=data.get("status_category", "unknown"),
                        is_running=False,
                        requires_attention=False,
                        last_update=data.get("last_update"),
                    )
                else:
                    logger.warning(f"[DevicePresenter] Unexpected type for {code}: {type(data)}")
                    continue
            except Exception as e:
                logger.error(f"[DevicePresenter] Failed to present device {code}: {e}")
                continue

        logger.debug(f"[DevicePresenter] Presented {len(result)} devices")
        return result

    def format_devices_to_ui(
        self,
        device_view_models: Dict[str, "DeviceViewModel"],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Format View Models to UI-ready dictionaries.

        Args:
            device_view_models: Dictionary from DeviceFacade.get_all_devices()

        Returns:
            Dictionary suitable for Qt widgets and managers
        """
        result = {}
        for code, vm in device_view_models.items():
            result[code] = {
                "device_id": vm.device_id,
                "display_name": vm.display_name,
                "status_code": vm.status_code,
                "status_display": vm.status_display,
                "status_emoji": vm.status_emoji,
                "status_color": vm.status_color,
                "status_category": vm.status_category,
                "is_running": vm.is_running,
                "requires_attention": vm.requires_attention,
                "last_update": vm.last_update,
                # Legacy field names (backward compatibility)
                "equip_code": vm.device_id,
                "equipment_code": vm.device_id,
                "name": vm.display_name,
                "status": vm.status_code,
                "color": vm.status_color,
            }
        logger.debug(f"[DevicePresenter] Formatted {len(result)} devices for UI")
        return result

    def format_single_device(
        self,
        device_vm: "DeviceViewModel",
    ) -> Dict[str, Any]:
        """
        Format single View Model to UI-ready dictionary.

        Args:
            device_vm: DeviceViewModel from DeviceFacade.get_device()

        Returns:
            Dictionary suitable for Qt widgets
        """
        result = {
            "device_id": device_vm.device_id,
            "display_name": device_vm.display_name,
            "status_code": device_vm.status_code,
            "status_display": device_vm.status_display,
            "status_emoji": device_vm.status_emoji,
            "status_color": device_vm.status_color,
            "status_category": device_vm.status_category,
            "is_running": device_vm.is_running,
            "requires_attention": device_vm.requires_attention,
            "last_update": device_vm.last_update,
            # Legacy fields
            "equip_code": device_vm.device_id,
            "equipment_code": device_vm.device_id,
            "name": device_vm.display_name,
            "status": device_vm.status_code,
            "color": device_vm.status_color,
        }
        logger.debug(f"[DevicePresenter] Formatted device {device_vm.device_id}")
        return result

    # ====== LEGACY COMPATIBILITY ======

    def format_device_legacy(self, dto_or_dict: Any) -> Dict[str, Any]:
        """
        Format device DTO or dict for display (legacy compatibility).

        Args:
            dto_or_dict: DeviceStatusDTO or dictionary (legacy format)

        Returns:
            Dictionary suitable for legacy UI widgets
        """
        # This method is for backward compatibility
        # New code should use DeviceFacade → format_devices_to_ui()
        if hasattr(dto_or_dict, "to_dict"):
            data = dto_or_dict.to_dict()
        elif isinstance(dto_or_dict, dict):
            data = dto_or_dict
        else:
            logger.warning(f"[DevicePresenter] Unknown format: {type(dto_or_dict)}")
            return {}

        return {
            "equip_code": data.get("equip_code", ""),
            "equipment_code": data.get("equip_code", ""),
            "status_code": str(data.get("status_code", "0")),
            "status_name": data.get("status_name", "unknown"),
            "status_display": data.get("status_display", "UNKNOWN"),
            "status_color": data.get("status_color", "#808080"),
            "last_update": data.get("last_update"),
            "is_running": data.get("is_running", False),
            "requires_attention": data.get("requires_attention", False),
            "name": data.get("equip_code", ""),
        }


__all__ = ["DevicePresenter"]
