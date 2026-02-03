# File: presentation/services/page_device_manager.py
"""
Page Device Manager.

Presentation Layer service that manages which devices are visible on each page.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal
from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


class PageDeviceManager(QObject):
    """
    Manages device visibility per page.
    """

    page_changed = Signal(str, list)  # (page_name, device_codes)
    devices_updated = Signal(str, list)  # (page_name, device_codes)

    def __init__(
        self,
        config_path: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._config_path = config_path or PATHS.device_positions_path
        self._current_page = "electrode_page"
        self._page_devices: Dict[str, List[str]] = {}
        self._all_devices: Set[str] = set()
        self._raw_config: Dict = {}

        self._load_config()

    def _load_config(self) -> None:
        """Load device positions from config file."""
        if not self._config_path or not self._config_path.exists():
            logger.warning(f"[PageDeviceManager] Config not found: {self._config_path}")
            return

        try:
            text = self._config_path.read_text(encoding="utf-8")
            self._raw_config = json.loads(text)

            for area_key, area_config in self._raw_config.items():
                if not isinstance(area_config, dict):
                    continue

                page_name = self._map_area_to_page(area_key)
                devices_section = area_config.get("devices", [])
                device_codes = self._extract_device_codes(devices_section)

                if device_codes:
                    if page_name not in self._page_devices:
                        self._page_devices[page_name] = []

                    existing = set(self._page_devices[page_name])
                    new_devices = [d for d in device_codes if d not in existing]

                    self._page_devices[page_name].extend(new_devices)
                    self._all_devices.update(device_codes)

                    logger.info(f"[PageDeviceManager] Loaded {len(device_codes)} devices " f"for {page_name} from {area_key}: {device_codes[:5]}...")

            for page, devices in self._page_devices.items():
                logger.info(f"[PageDeviceManager] {page}: {len(devices)} devices total")

            total = len(self._all_devices)
            logger.info(f"[PageDeviceManager] Loaded {total} total unique devices from config")

        except Exception as e:
            logger.error(f"[PageDeviceManager] Failed to load config: {e}")

    def _extract_device_codes(self, devices_section) -> List[str]:
        """Extract device codes from config section."""
        device_codes = []

        if isinstance(devices_section, list):
            for dev in devices_section:
                if isinstance(dev, dict):
                    device_id = dev.get("id") or dev.get("device_code") or dev.get("code") or dev.get("device_id")
                    if device_id:
                        device_codes.append(device_id)
                elif isinstance(dev, str):
                    device_codes.append(dev)

        elif isinstance(devices_section, dict):
            meta_keys = {"ref_width", "ref_height", "min_scale", "max_scale"}
            for key in devices_section:
                if key not in meta_keys:
                    device_codes.append(key)

        return device_codes

    def _map_area_to_page(self, area_key: str) -> str:
        """Map area key from config to page name."""
        area_lower = area_key.lower()

        if "electrode" in area_lower:
            return "electrode_page"
        if "assembly" in area_lower:
            return "assembly_page"
        if "daboard" in area_lower or "dashboard" in area_lower:
            return "electrode_page"
        if "order" in area_lower:
            return "assembly_page"

        logger.warning(f"[PageDeviceManager] Unknown area key: {area_key}")
        return "electrode_page"

    def set_current_page(self, page_name: str) -> List[str]:
        """Set current page and emit signal."""
        normalized = self._normalize_page_name(page_name)

        if normalized != self._current_page:
            self._current_page = normalized
            devices = self.get_page_devices(normalized)

            logger.info(f"[PageDeviceManager] Page changed to {normalized}: " f"{len(devices)} devices")

            self.page_changed.emit(normalized, devices)
            return devices

        return self.get_current_devices()

    def force_load_current_page(self) -> List[str]:
        """
        Force emit page_changed signal for current page.

        Used for initial load when page hasn't changed but we need to trigger
        the signal for DeviceListViewModel to start loading.
        """
        devices = self.get_page_devices(self._current_page)

        logger.info(f"[PageDeviceManager] Force loading {self._current_page}: " f"{len(devices)} devices")

        self.page_changed.emit(self._current_page, devices)
        return devices

    def _normalize_page_name(self, page_name: str) -> str:
        """Normalize page name to consistent format."""
        normalized = page_name.replace("daboard", "electrode")
        if not normalized.endswith("_page"):
            normalized = f"{normalized}_page"
        return normalized

    def get_current_page(self) -> str:
        """Get the current page name."""
        return self._current_page

    def get_current_devices(self) -> List[str]:
        """Get device IDs for the current page."""
        return self.get_page_devices(self._current_page)

    def get_page_devices(self, page_name: str) -> List[str]:
        """Get device IDs for a specific page."""
        normalized = self._normalize_page_name(page_name)
        devices = self._page_devices.get(normalized, [])
        return list(devices)

    def get_all_devices(self) -> List[str]:
        """Get all known device IDs across all pages."""
        return list(self._all_devices)

    def get_page_count(self) -> int:
        """Get number of configured pages."""
        return len(self._page_devices)

    def get_device_count(self, page_name: Optional[str] = None) -> int:
        """Get device count for a page or all pages."""
        if page_name:
            return len(self.get_page_devices(page_name))
        return len(self._all_devices)

    def get_layout_config(self, area_key: str) -> Dict:
        """Get raw layout config for an area key."""
        return self._raw_config.get(area_key, {})


__all__ = ["PageDeviceManager"]
