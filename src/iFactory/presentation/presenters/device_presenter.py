# File: presentation/presenters/device_presenter.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from ..constants.status import Status, StatusCode
from ..viewmodels.device import DeviceViewModel

logger = logging.getLogger(__name__)


class DevicePresenter:
    def present_many(self, dtos: Dict[str, Any]) -> Dict[str, DeviceViewModel]:
        result: Dict[str, DeviceViewModel] = {}
        for code, dto in dtos.items():
            try:
                result[code] = self.present_one(dto)
            except Exception as e:
                logger.warning("Failed to present device %s: %s", code, e)
                result[code] = DeviceViewModel.empty(code)
        return result

    def present_one(self, dto: Any) -> DeviceViewModel:
        code = self._get(dto, "equip_code", "code", default="UNKNOWN")
        name = self._get(dto, "name", default=None)
        description = self._get(dto, "description", default="")
        last_update = self._get(dto, "last_update", default=None)
        raw_status = self._get(dto, "status_code", default=0)

        batch = self._get(dto, "material_batch", default="--")
        feeding = self._get(dto, "feeding_time", default=None)
        input_count = self._get(dto, "input_count", default=0) or 0
        output_count = self._get(dto, "output_count", default=0) or 0
        error_count = self._get(dto, "error_count", default=0) or 0

        status_code = self._parse_status(raw_status)
        status_name = Status.get_name(status_code)
        status_color = Status.get_color(status_code)
        status_emoji = Status.get_emoji(status_code)

        display_name = f"{name} ({code})" if name else code
        last_update_str = last_update.isoformat() if hasattr(last_update, "isoformat") else None
        feeding_str = feeding.strftime("%H:%M:%S") if hasattr(feeding, "strftime") else "--"

        return DeviceViewModel(
            device_id=code,
            display_name=display_name,
            status_code=status_code,
            status_name=status_name,
            status_color=status_color,
            status_emoji=status_emoji,
            is_running=(status_code == StatusCode.RUNNING),
            requires_attention=(status_code in (StatusCode.STOPPED, StatusCode.ALARM)),
            last_update=last_update_str,
            input_count=input_count,
            output_count=output_count,
            error_count=error_count,
            description=description,
            material_batch=batch,
            feeding_time=feeding_str,
        )

    def _get(self, data: Any, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if isinstance(data, dict) and key in data:
                return data[key]
            if hasattr(data, key):
                return getattr(data, key)
        return default

    def _parse_status(self, raw: Union[str, int, None]) -> int:
        if raw is None:
            return StatusCode.UNKNOWN
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (ValueError, TypeError):
            return StatusCode.UNKNOWN
