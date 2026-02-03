# File: presentation/services/page_device_manager.py
"""
Page Device Manager.

Presentation Layer service that manages which devices are visible on each page.
This is a UI concept - it determines which device IDs to pass to the Application Layer.

Responsibilities:
- Load device-to-page mappings from configuration
- Track current page state
- Emit signals when page changes (for UI coordination)
- Provide device IDs for the current page to controllers
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

    This is a Presentation Layer service that:
    1. Knows which devices belong to which UI pages
    2. Tracks the current page
    3. Provides device IDs to controllers for sync operations

    The Application Layer (SyncOrchestrator) receives explicit device IDs
    from controllers - it has no knowledge of "pages".
    """

    # Signals for UI coordination
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
                    device_codes = self._extract_device_codes(devices_list)

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

    def _extract_device_codes(self, devices_list: List) -> List[str]:
        """Extract device codes from config list."""
        device_codes = []
        for dev in devices_list:
            if isinstance(dev, dict):
                device_id = dev.get("id") or dev.get("device_code") or dev.get("code")
                if device_id:
                    device_codes.append(device_id)
            elif isinstance(dev, str):
                device_codes.append(dev)
        return device_codes

    def _map_area_to_page(self, area_key: str) -> str:
        """Map area key from config to page name."""
        area_lower = area_key.lower()

        if "electrode" in area_lower or "daboard" in area_lower:
            return "electrode_page"
        elif "order" in area_lower:
            return "assembly_page"
        else:
            return "electrode_page"

    def set_current_page(self, page_name: str) -> List[str]:
        """
        Set current page and return devices for that page.

        Emits page_changed signal for UI coordination.
        Controllers listen to this signal and call sync with the device IDs.

        Args:
            page_name: Name of the page to switch to.

        Returns:
            List of device IDs for the new page.
        """
        normalized = self._normalize_page_name(page_name)

        if normalized != self._current_page:
            self._current_page = normalized
            devices = self.get_page_devices(normalized)

            logger.info(f"[PageDeviceManager] Page changed to {normalized}: " f"{len(devices)} devices")

            # Emit signal - controllers will handle sync
            self.page_changed.emit(normalized, devices)

            return devices

        return self.get_current_devices()

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
        """
        Get device IDs for the current page.

        This is the primary method controllers use to get device IDs
        to pass to the Application Layer.
        """
        return self.get_page_devices(self._current_page)

    def get_page_devices(self, page_name: str) -> List[str]:
        """Get device IDs for a specific page."""
        normalized = self._normalize_page_name(page_name)
        return list(self._page_devices.get(normalized, []))

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


__all__ = ["PageDeviceManager"]
