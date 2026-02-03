# File: infrastructure/adapters/device_file_adapter.py
import json
import logging
from typing import Dict, List, Optional, Any

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


class DeviceFileAdapter:
    """
    Read-only Adapter for device configuration files (JSON).

    Supports mapping between:
    - display_id (id): Used for UI display (e.g., ALS01)
    - remote_id: Used for database queries (e.g., ASL01)
    """

    def __init__(self) -> None:
        self._path = PATHS.device_positions_path
        self._cache: Optional[Dict[str, Any]] = None
        self._display_to_remote: Optional[Dict[str, str]] = None
        self._remote_to_display: Optional[Dict[str, str]] = None

    def _load_data(self) -> Dict[str, Any]:
        """Reads file from disk with caching."""
        if self._cache is not None:
            return self._cache

        if not self._path.exists():
            logger.warning(f"Device config not found at {self._path}")
            return {}
        try:
            self._cache = json.loads(self._path.read_text(encoding="utf-8"))
            return self._cache
        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            return {}

    def _build_mappings(self) -> None:
        """Build display <-> remote ID mappings from config."""
        if self._display_to_remote is not None:
            return  # Already built

        self._display_to_remote = {}
        self._remote_to_display = {}

        data = self._load_data()

        for page_key, page_config in data.items():
            if not isinstance(page_config, dict):
                continue

            devices = page_config.get("devices", [])
            for device in devices:
                display_id = device.get("id", "").upper()
                # Use remote_id if specified, otherwise fallback to id
                remote_id = device.get("remote_id", display_id).upper()

                if display_id:
                    self._display_to_remote[display_id] = remote_id
                    self._remote_to_display[remote_id] = display_id

    def get_page_devices(self, page: str) -> List[str]:
        """Get display IDs for a page."""
        data = self._load_data()
        page_config = data.get(page, {})
        if isinstance(page_config, dict):
            devices = page_config.get("devices", [])
            return [d.get("id", "") for d in devices if d.get("id")]
        return data.get("pages", {}).get(page, [])

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        """Get all pages with their display device IDs."""
        data = self._load_data()
        result = {}
        for page_key, page_config in data.items():
            if isinstance(page_config, dict) and "devices" in page_config:
                result[page_key] = [d.get("id", "") for d in page_config.get("devices", []) if d.get("id")]
        return result if result else data.get("pages", {})

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device info by display ID."""
        data = self._load_data()

        # Search in all pages
        for page_key, page_config in data.items():
            if not isinstance(page_config, dict):
                continue
            devices = page_config.get("devices", [])
            for device in devices:
                if device.get("id", "").upper() == device_id.upper():
                    return device

        return data.get("devices", {}).get(device_id)

    # =========================================================================
    # NEW: Mapping Methods for remote_id <-> display_id
    # =========================================================================

    def get_display_to_remote_mapping(self) -> Dict[str, str]:
        """
        Get mapping from display_id to remote_id.

        Returns:
            Dict mapping display IDs (e.g., "ALS01") to remote IDs (e.g., "ASL01")
        """
        self._build_mappings()
        return self._display_to_remote.copy()

    def get_remote_to_display_mapping(self) -> Dict[str, str]:
        """
        Get mapping from remote_id to display_id.

        Returns:
            Dict mapping remote IDs (e.g., "ASL01") to display IDs (e.g., "ALS01")
        """
        self._build_mappings()
        return self._remote_to_display.copy()

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        """
        Convert display IDs to remote IDs for database queries.

        Args:
            display_ids: List of display IDs (e.g., ["ALS01", "ALS02"])

        Returns:
            List of remote IDs (e.g., ["ASL01", "ASL02"])
        """
        self._build_mappings()
        return [self._display_to_remote.get(did.upper(), did.upper()) for did in display_ids]

    def to_display_id(self, remote_id: str) -> str:
        """
        Convert a single remote_id to display_id.

        Args:
            remote_id: Remote ID from database (e.g., "ASL01")

        Returns:
            Display ID for UI (e.g., "ALS01")
        """
        self._build_mappings()
        return self._remote_to_display.get(remote_id.upper(), remote_id.upper())

    def to_remote_id(self, display_id: str) -> str:
        """
        Convert a single display_id to remote_id.

        Args:
            display_id: Display ID from UI (e.g., "ALS01")

        Returns:
            Remote ID for database (e.g., "ASL01")
        """
        self._build_mappings()
        return self._display_to_remote.get(display_id.upper(), display_id.upper())

    def invalidate_cache(self) -> None:
        """Clear cached data (call when config file changes)."""
        self._cache = None
        self._display_to_remote = None
        self._remote_to_display = None
