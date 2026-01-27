"""
Device Presenter - Transforms Application DTOs to ViewModels.
Pure transformation layer - NO domain imports, NO side effects.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..constants.ui_constants import StatusColors
from ..viewmodels.device_vm import DeviceViewModel

logger = logging.getLogger(__name__)


class DevicePresenter:
    """Maps DTOs to UI-agnostic ViewModels."""

    def __init__(self, theme: str = "light"):
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"

    def present_device_list(
        self,
        statuses: Dict[str, Any],
    ) -> Dict[str, DeviceViewModel]:
        """Transform map of DTOs to ViewModels."""
        return {code: self.present_single_device(data) for code, data in statuses.items()}

    def present_single_device(self, data: Any) -> DeviceViewModel:
        """Transform single DTO to ViewModel."""
        code = getattr(data, "equip_code", "UNKNOWN")
        last_update = getattr(data, "last_update", None)

        raw_status = getattr(data, "status_code", 0)
        status_code = self._parse_status_code(raw_status)

        return DeviceViewModel(
            device_id=code,
            display_name=code,
            status_code=str(status_code),
            status_display=StatusColors.get_name(status_code),
            status_color=StatusColors.get_color(status_code, self._theme),
            status_emoji=self._get_status_emoji(status_code),
            is_running=(status_code == StatusColors.RUNNING),
            requires_attention=(status_code in (StatusColors.STOPPED, StatusColors.ALARM)),
            last_update=last_update.isoformat() if last_update else None,
        )

    def _parse_status_code(self, raw: Any) -> int:
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0

    def _get_status_emoji(self, status_code: int) -> str:
        emojis = {
            0: "❓",
            1: "🟢",
            2: "⬛",
            3: "🔴",
            4: "🔧",
            5: "⚠️",
        }
        return emojis.get(status_code, "")


__all__ = ["DevicePresenter"]
