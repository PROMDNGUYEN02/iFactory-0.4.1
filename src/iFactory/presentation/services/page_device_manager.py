# src/iFactory/presentation/services/page_device_manager.py
"""
Page Device Manager - Enhanced with missing methods.

Presentation Layer service that manages which devices are visible on each page.

FIXES v2.0:
- Added get_all_page_devices() method
- Added current_page property
- Added get_all_page_names() method
- Improved error handling
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal

try:
    from iFactory.infrastructure.configuration.paths import PATHS
except ImportError:
    PATHS = None

logger = logging.getLogger(__name__)


class PageDeviceManager(QObject):
    """
    Manages device visibility per page.

    Features:
    - Page-to-device mapping
    - Device layout configurations
    - Navigation signals
    - Config-based device loading
    """

    # Signals
    page_changed = Signal(str, list)  # (page_name, device_codes)
    devices_updated = Signal(str, list)  # (page_name, device_codes)

    def __init__(
        self,
        config_path: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        # Configuration
        self._config_path = config_path or (PATHS.device_positions_path if PATHS else None)

        # State
        self._current_page = "electrode_page"
        self._page_devices: Dict[str, List[str]] = {}
        self._all_devices: Set[str] = set()
        self._raw_config: Dict = {}

        # Layout configs per area
        self._layout_configs: Dict[str, Dict[str, Any]] = {}

        self._load_config()

    # =========================================================================
    # Configuration Loading
    # =========================================================================

    def _load_config(self) -> None:
        """Load device positions from config file."""
        if not self._config_path:
            logger.warning("[PageDeviceManager] No config path provided")
            return

        if not self._config_path.exists():
            logger.warning(f"[PageDeviceManager] Config not found: {self._config_path}")
            return

        try:
            text = self._config_path.read_text(encoding="utf-8")
            self._raw_config = json.loads(text)

            for area_key, area_config in self._raw_config.items():
                if not isinstance(area_config, dict):
                    continue

                # Store layout config
                self._layout_configs[area_key] = area_config

                # Map to page
                page_name = self._map_area_to_page(area_key)

                # Extract devices
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

            # Summary
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
            # Dict format - keys are device codes, skip meta keys
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

        logger.warning(f"[PageDeviceManager] Unknown area key: {area_key}, defaulting to electrode_page")
        return "electrode_page"

    def _normalize_page_name(self, page_name: str) -> str:
        """Normalize page name to consistent format."""
        normalized = page_name.replace("daboard", "electrode")
        if not normalized.endswith("_page"):
            normalized = f"{normalized}_page"
        return normalized

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def current_page(self) -> str:
        """Get current page name."""
        return self._current_page

    @current_page.setter
    def current_page(self, value: str) -> None:
        """Set current page name."""
        normalized = self._normalize_page_name(value)
        if normalized in self._page_devices:
            self._current_page = normalized

    # =========================================================================
    # Public API - Page Navigation
    # =========================================================================

    def set_current_page(self, page_name: str) -> List[str]:
        """
        Set current page and emit signal.

        Returns:
            List of device IDs for the page
        """
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

        Returns:
            List of device IDs for current page
        """
        devices = self.get_page_devices(self._current_page)

        logger.info(f"[PageDeviceManager] Force loading {self._current_page}: " f"{len(devices)} devices")

        self.page_changed.emit(self._current_page, devices)
        return devices

    # =========================================================================
    # Public API - Device Queries
    # =========================================================================

    def get_current_page(self) -> str:
        """Get the current page name."""
        return self._current_page

    def get_current_devices(self) -> List[str]:
        """Get device IDs for the current page."""
        return self.get_page_devices(self._current_page)

    def get_page_devices(self, page_name: str) -> List[str]:
        """
        Get device IDs for a specific page.

        Args:
            page_name: Name of the page

        Returns:
            List of device IDs for that page
        """
        normalized = self._normalize_page_name(page_name)
        devices = self._page_devices.get(normalized, [])
        return list(devices)

    def get_all_devices(self) -> List[str]:
        """
        Get all known device IDs across all pages.

        Returns:
            List of all unique device IDs
        """
        return list(self._all_devices)

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        """
        Get all page-to-devices mappings.

        Returns:
            Dict mapping page_name to list of device_ids
        """
        return self._page_devices.copy()

    def get_all_page_names(self) -> List[str]:
        """
        Get list of all configured page names.

        Returns:
            List of page names
        """
        return list(self._page_devices.keys())

    def get_page_count(self) -> int:
        """
        Get number of configured pages.

        Returns:
            Number of pages
        """
        return len(self._page_devices)

    def get_device_count(self, page_name: Optional[str] = None) -> int:
        """
        Get device count for a page or all pages.

        Args:
            page_name: Page name, or None for total count

        Returns:
            Device count
        """
        if page_name:
            return len(self.get_page_devices(page_name))
        return len(self._all_devices)

    # =========================================================================
    # Public API - Layout Config
    # =========================================================================

    def get_layout_config(self, area_key: str) -> Dict:
        """
        Get raw layout config for an area key.

        Args:
            area_key: Area identifier from config

        Returns:
            Layout configuration dict
        """
        return self._layout_configs.get(area_key, {})

    def get_page_layout_configs(self, page_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all layout configs for areas on a page.

        Args:
            page_name: Page name

        Returns:
            Dict mapping area_key to layout config
        """
        # Find all areas that map to this page
        normalized = self._normalize_page_name(page_name)
        configs = {}

        for area_key in self._layout_configs:
            if self._map_area_to_page(area_key) == normalized:
                configs[area_key] = self._layout_configs[area_key]

        return configs

    def get_device_area(self, device_id: str) -> Optional[str]:
        """
        Get the area key that contains a device.

        Args:
            device_id: Device identifier

        Returns:
            Area key or None if not found
        """
        for area_key, config in self._layout_configs.items():
            devices = config.get("devices", [])

            if isinstance(devices, list):
                for dev in devices:
                    if isinstance(dev, dict):
                        if dev.get("id") == device_id:
                            return area_key
                    elif dev == device_id:
                        return area_key

        return None

    def is_device_on_page(self, device_id: str, page_name: str) -> bool:
        """
        Check if a device belongs to a page.

        Args:
            device_id: Device identifier
            page_name: Page name

        Returns:
            True if device is on page
        """
        normalized = self._normalize_page_name(page_name)
        return device_id in self._page_devices.get(normalized, [])

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.

        Returns:
            Dict with statistics
        """
        return {
            "current_page": self._current_page,
            "total_pages": len(self._page_devices),
            "total_devices": len(self._all_devices),
            "total_areas": len(self._layout_configs),
            "pages": {name: len(devices) for name, devices in self._page_devices.items()},
        }


__all__ = ["PageDeviceManager"]
