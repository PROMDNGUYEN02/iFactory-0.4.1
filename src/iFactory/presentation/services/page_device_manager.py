"""
Page Device Manager.
Manages which devices are visible on each page.
Triggers sync when page changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class PageDeviceManager(QObject):
    """
    Manages device visibility per page.
    Emits signals when page changes to trigger sync.
    """

    page_changed = Signal(str, list)  # page_name, device_codes
    devices_updated = Signal(str, list)

    def __init__(
        self,
        config_path: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._config_path = config_path
        self._current_page = "dashboard_page"  # Default page
        self._page_devices: Dict[str, List[str]] = {}
        self._all_devices: Set[str] = set()

        self._load_config()

    def _load_config(self) -> None:
        """Load device positions from config file."""
        if not self._config_path or not self._config_path.exists():
            logger.warning(f"[PageDeviceManager] Config not found: {self._config_path}")
            return

        try:
            text = self._config_path.read_text(encoding="utf-8")
            data = json.loads(text)

            for area_key, area_config in data.items():
                if not isinstance(area_config, dict):
                    continue

                page_name = self._map_area_to_page(area_key)
                devices_list = area_config.get("devices", [])

                if isinstance(devices_list, list):
                    device_codes = []
                    for dev in devices_list:
                        if isinstance(dev, dict):
                            device_id = dev.get("id") or dev.get("device_code") or dev.get("code")
                            if device_id:
                                device_codes.append(device_id)

                    if device_codes:
                        if page_name not in self._page_devices:
                            self._page_devices[page_name] = []

                        self._page_devices[page_name].extend(device_codes)
                        self._all_devices.update(device_codes)

                        logger.info(f"[PageDeviceManager] Loaded {len(device_codes)} devices " f"for {page_name}: {device_codes}")

            total = len(self._all_devices)
            logger.info(f"[PageDeviceManager] Loaded {total} total unique devices from config")

        except Exception as e:
            logger.error(f"[PageDeviceManager] Failed to load config: {e}")

    def _map_area_to_page(self, area_key: str) -> str:
        """Map area key from config to page name."""
        area_lower = area_key.lower()

        if "dashboard" in area_lower or "daboard" in area_lower:
            return "dashboard_page"
        elif "order" in area_lower:
            return "orders_page"
        else:
            return "dashboard_page"

    def set_current_page(self, page_name: str) -> List[str]:
        """
        Set current page and return devices for that page.
        Emits page_changed signal to trigger sync.
        """
        normalized = page_name.replace("daboard", "dashboard")
        if not normalized.endswith("_page"):
            normalized = f"{normalized}_page"

        if normalized != self._current_page:
            self._current_page = normalized
            devices = self.get_page_devices(normalized)

            logger.info(f"[PageDeviceManager] Page changed to {normalized}: " f"{len(devices)} devices")
            self.page_changed.emit(normalized, devices)

            return devices

        return self.get_current_devices()

    def get_current_page(self) -> str:
        return self._current_page

    def get_current_devices(self) -> List[str]:
        return self.get_page_devices(self._current_page)

    def get_page_devices(self, page_name: str) -> List[str]:
        normalized = page_name.replace("daboard", "dashboard")
        return self._page_devices.get(normalized, [])

    def get_all_devices(self) -> List[str]:
        return list(self._all_devices)


__all__ = ["PageDeviceManager"]
