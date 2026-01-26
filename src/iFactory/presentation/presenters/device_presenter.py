"""
Device Presenter - Transforms Application DTOs to pure ViewModels.
"""

from __future__ import annotations
import logging
from typing import Dict, Any
from ..viewmodels.device_vm import DeviceViewModel

logger = logging.getLogger(__name__)


class DevicePresenter:
    """
    Pure transformation layer. Maps DTOs to UI-agnostic ViewModels.
    """

    def present_device_list(self, statuses: Dict[str, Any]) -> Dict[str, DeviceViewModel]:
        """
        Transforms a map of Application DTOs into strictly UI ViewModels.
        """
        result = {}
        for code, data in statuses.items():
            result[code] = self.present_single_device(data)
        return result

    def present_single_device(self, data: Any) -> DeviceViewModel:
        """
        Transforms a single Application DTO.
        """
        code = getattr(data, "equip_code", "UNKNOWN")
        last_update = getattr(data, "last_update", None)

        return DeviceViewModel(
            device_id=code,
            display_name=code,
            status_code=str(getattr(data, "status_code", "0")),
            status_display=getattr(data, "status_display", "Unknown"),
            status_color=getattr(data, "status_color", "#808080"),
            status_emoji="",
            is_running=getattr(data, "is_running", False),
            requires_attention=getattr(data, "requires_attention", False),
            last_update=last_update.isoformat() if last_update else None,
        )
