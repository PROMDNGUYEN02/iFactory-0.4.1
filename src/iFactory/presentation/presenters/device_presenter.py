"""
Device Presenter - Transforms Application DTOs to ViewModels.
Pure transformation layer - NO domain imports, NO side effects.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Union
from ..constants.ui_constants import StatusColors
from ..viewmodels.device_vm import DeviceViewModel

logger = logging.getLogger(__name__)


class DevicePresenter:
    """
    Responsible for converting raw Device DTOs into UI-ready DeviceViewModels.
    """

    def __init__(self, theme: str = "light"):
        # Theme is now handled globally by ThemeManager, but we keep init signature for compatibility
        pass

    def set_theme(self, theme: str) -> None:
        """Deprecated: Theme is now handled globally."""
        pass

    def present_device_list(self, dtos: Dict[str, Any]) -> Dict[str, DeviceViewModel]:
        result = {}
        for code, data in dtos.items():
            try:
                vm = self.present_single_device(data)
                result[code] = vm
            except Exception as e:
                logger.warning(f"Failed to present device {code}: {e}")
                result[code] = self._create_fallback_vm(code)
        return result

    def present_single_device(self, data: Any) -> DeviceViewModel:
        # 1. Normalize Input
        code = self._extract_attr(data, "equip_code", "code", default="UNKNOWN")
        last_update = self._extract_attr(data, "last_update", default=None)
        raw_status = self._extract_attr(data, "status_code", default="0")

        # 2. Resolve UI Logic
        status_code = self._parse_status_code(raw_status)

        # [FIXED] Call get_color with ONLY status_code.
        status_color = StatusColors.get_color(status_code)
        status_name = StatusColors.get_name(status_code)

        # 3. Build ViewModel
        return DeviceViewModel(
            device_id=code,
            display_name=code,
            status_code=str(status_code),
            status_display=status_name,
            status_color=status_color,
            status_emoji=self._get_status_emoji(status_code),
            is_running=(status_code == StatusColors.RUNNING),
            requires_attention=(status_code in (StatusColors.STOPPED, StatusColors.ALARM)),
            last_update=last_update.isoformat() if last_update else None,
        )

    def _create_fallback_vm(self, code: str) -> DeviceViewModel:
        return DeviceViewModel(
            device_id=code,
            display_name=code,
            status_code="0",
            status_display="Unknown",
            status_color=StatusColors.get_color(0),  # [FIXED] No theme arg
            status_emoji="❓",
            is_running=False,
            requires_attention=False,
            last_update=None,
        )

    def _extract_attr(self, data: Any, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if isinstance(data, dict):
                if key in data:
                    return data[key]
            else:
                if hasattr(data, key):
                    return getattr(data, key)
        return default

    def _parse_status_code(self, raw: Union[str, int]) -> int:
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0

    def _get_status_emoji(self, status_code: int) -> str:
        emojis = {0: "❓", 1: "🟢", 2: "⬛", 3: "🔴", 4: "🔧", 5: "⚠️"}
        return emojis.get(status_code, "❓")
