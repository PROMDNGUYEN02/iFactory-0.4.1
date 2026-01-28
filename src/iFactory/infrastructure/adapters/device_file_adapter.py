"""
Infrastructure: Device File Adapter.
Reads device positions and metadata from the filesystem.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


class DeviceFileAdapter:
    """
    Adapter for device_positions.json.
    """

    def __init__(self) -> None:
        self._path = PATHS.device_positions_path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self._path.exists():
            logger.warning(f"Device config not found at {self._path}")
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            return {}

    def get_page_devices(self, page: str) -> List[str]:
        """Get list of device IDs for a specific page."""
        return self._data.get("pages", {}).get(page, [])

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        """Get mapping of all pages to device IDs."""
        return self._data.get("pages", {})

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific device."""
        return self._data.get("devices", {}).get(device_id)
