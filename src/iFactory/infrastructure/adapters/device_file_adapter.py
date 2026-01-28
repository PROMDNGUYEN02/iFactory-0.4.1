import json
import logging
from typing import Dict, List, Optional, Any

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


class DeviceFileAdapter:
    """
    Read-only Adapter for device configuration files (JSON).
    """

    def __init__(self) -> None:
        self._path = PATHS.device_positions_path

    def _load_data(self) -> Dict[str, Any]:
        """Reads file from disk on demand or caches if appropriate."""
        if not self._path.exists():
            logger.warning(f"Device config not found at {self._path}")
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            return {}

    def get_page_devices(self, page: str) -> List[str]:
        data = self._load_data()
        return data.get("pages", {}).get(page, [])

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        data = self._load_data()
        return data.get("pages", {})

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        data = self._load_data()
        return data.get("devices", {}).get(device_id)
