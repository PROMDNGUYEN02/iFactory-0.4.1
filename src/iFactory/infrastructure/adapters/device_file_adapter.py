# src/iFactory/infrastructure/adapters/device_file_adapter.py
"""
Infrastructure: Device File Adapter.

Read-only adapter for device configuration files with caching
and optional file watching for auto-reload.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DeviceInfo:
    """Device information from configuration."""

    id: str
    remote_id: str
    name: Optional[str] = None
    type: Optional[str] = None
    position: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceInfo":
        """Create DeviceInfo from dictionary."""
        device_id = data.get("id", "").upper()
        return cls(
            id=device_id,
            remote_id=data.get("remote_id", device_id).upper(),
            name=data.get("name"),
            type=data.get("type"),
            position=data.get("position"),
            metadata={k: v for k, v in data.items() if k not in ("id", "remote_id", "name", "type", "position")},
        )


@dataclass
class CacheStats:
    """Statistics about the device adapter cache."""

    loaded_at: Optional[datetime] = None
    device_count: int = 0
    page_count: int = 0
    mapped_count: int = 0

    @property
    def is_loaded(self) -> bool:
        return self.loaded_at is not None


# ============================================================================
# Device File Adapter
# ============================================================================


class DeviceFileAdapter:
    """
    Read-only Adapter for device configuration files (JSON).

    Features:
    - Caching with manual invalidation
    - ID mapping (display_id <-> remote_id)
    - Thread-safe operations
    - Rich device info extraction

    ID Mapping:
    - display_id (id): Used for UI display (e.g., ALS01)
    - remote_id: Used for database queries (e.g., ASL01)

    Usage:
        adapter = DeviceFileAdapter()

        # Get device IDs for a page
        devices = adapter.get_page_devices("electrode_page")

        # Convert display IDs to remote IDs
        remote_ids = adapter.to_remote_ids(["ALS01", "ALS02"])

        # Convert remote ID back to display ID
        display_id = adapter.to_display_id("ASL01")
    """

    __slots__ = (
        "_path",
        "_cache",
        "_display_to_remote",
        "_remote_to_display",
        "_device_info_cache",
        "_lock",
        "_stats",
        "_on_reload_callbacks",
    )

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """
        Initialize DeviceFileAdapter.

        Args:
            config_path: Path to device positions JSON file.
                        Defaults to PATHS.device_positions_path.
        """
        self._path = config_path or PATHS.device_positions_path
        self._cache: Optional[Dict[str, Any]] = None
        self._display_to_remote: Optional[Dict[str, str]] = None
        self._remote_to_display: Optional[Dict[str, str]] = None
        self._device_info_cache: Dict[str, DeviceInfo] = {}
        self._lock = threading.RLock()
        self._stats = CacheStats()
        self._on_reload_callbacks: List[Callable[[], None]] = []

    # ========================================================================
    # Cache Management
    # ========================================================================

    def _load_data(self) -> Dict[str, Any]:
        """Load and cache data from file."""
        with self._lock:
            if self._cache is not None:
                return self._cache

            if not self._path.exists():
                logger.warning(f"Device config not found at {self._path}")
                return {}

            try:
                content = self._path.read_text(encoding="utf-8")
                self._cache = json.loads(content)
                self._stats.loaded_at = datetime.now()

                logger.info(f"[DeviceFileAdapter] Loaded config from {self._path}")
                return self._cache

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in device config: {e}")
                return {}
            except Exception as e:
                logger.error(f"Failed to load device config: {e}")
                return {}

    def _build_mappings(self) -> None:
        """Build ID mappings from configuration."""
        with self._lock:
            if self._display_to_remote is not None:
                return

            self._display_to_remote = {}
            self._remote_to_display = {}
            self._device_info_cache = {}

            data = self._load_data()
            device_count = 0
            page_count = 0

            for page_key, page_config in data.items():
                if not isinstance(page_config, dict):
                    continue

                devices = page_config.get("devices", [])
                if not devices:
                    continue

                page_count += 1

                for device_data in devices:
                    if not isinstance(device_data, dict):
                        continue

                    display_id = device_data.get("id", "").upper()
                    if not display_id:
                        continue

                    remote_id = device_data.get("remote_id", display_id).upper()

                    self._display_to_remote[display_id] = remote_id
                    self._remote_to_display[remote_id] = display_id

                    # Cache device info
                    self._device_info_cache[display_id] = DeviceInfo.from_dict(device_data)
                    device_count += 1

            # Update stats
            mapped_count = sum(1 for d, r in self._display_to_remote.items() if d != r)
            self._stats.device_count = device_count
            self._stats.page_count = page_count
            self._stats.mapped_count = mapped_count

            if mapped_count > 0:
                logger.info(f"[DeviceFileAdapter] {device_count} devices, " f"{mapped_count} with ID mapping")

    def invalidate_cache(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._cache = None
            self._display_to_remote = None
            self._remote_to_display = None
            self._device_info_cache.clear()
            self._stats = CacheStats()

            logger.debug("[DeviceFileAdapter] Cache invalidated")

            # Notify callbacks
            for callback in self._on_reload_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Reload callback error: {e}")

    def reload(self) -> None:
        """Reload configuration from file."""
        self.invalidate_cache()
        self._load_data()
        self._build_mappings()

    def on_reload(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when cache is invalidated."""
        self._on_reload_callbacks.append(callback)

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    # ========================================================================
    # Page & Device Queries
    # ========================================================================

    def get_page_devices(self, page: str) -> List[str]:
        """
        Get display IDs for a specific page.

        Args:
            page: Page key (e.g., "electrode_page")

        Returns:
            List of display device IDs
        """
        data = self._load_data()
        page_config = data.get(page, {})

        if isinstance(page_config, dict):
            devices = page_config.get("devices", [])
            return [d.get("id", "") for d in devices if isinstance(d, dict) and d.get("id")]

        # Fallback for legacy format
        return data.get("pages", {}).get(page, [])

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        """
        Get all pages with their device IDs.

        Returns:
            Dict mapping page names to lists of display device IDs
        """
        data = self._load_data()
        result = {}

        for page_key, page_config in data.items():
            if isinstance(page_config, dict) and "devices" in page_config:
                devices = [d.get("id", "") for d in page_config.get("devices", []) if isinstance(d, dict) and d.get("id")]
                if devices:
                    result[page_key] = devices

        return result if result else data.get("pages", {})

    def get_all_devices(self) -> List[str]:
        """
        Get all device display IDs across all pages.

        Returns:
            List of unique display device IDs
        """
        self._build_mappings()
        return list(self._display_to_remote.keys())

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device information by display ID.

        Args:
            device_id: Display device ID

        Returns:
            Device configuration dictionary or None
        """
        self._build_mappings()

        info = self._device_info_cache.get(device_id.upper())
        if info:
            return {
                "id": info.id,
                "remote_id": info.remote_id,
                "name": info.name,
                "type": info.type,
                "position": info.position,
                **info.metadata,
            }

        # Fallback: search in raw data
        data = self._load_data()
        for page_config in data.values():
            if not isinstance(page_config, dict):
                continue
            for device in page_config.get("devices", []):
                if device.get("id", "").upper() == device_id.upper():
                    return device

        return None

    def get_device_info_typed(self, device_id: str) -> Optional[DeviceInfo]:
        """
        Get typed device information.

        Args:
            device_id: Display device ID

        Returns:
            DeviceInfo instance or None
        """
        self._build_mappings()
        return self._device_info_cache.get(device_id.upper())

    # ========================================================================
    # ID Mapping Methods
    # ========================================================================

    def get_display_to_remote_mapping(self) -> Dict[str, str]:
        """
        Get complete mapping from display_id to remote_id.

        Returns:
            Dict mapping display IDs to remote IDs
        """
        self._build_mappings()
        return self._display_to_remote.copy()

    def get_remote_to_display_mapping(self) -> Dict[str, str]:
        """
        Get complete mapping from remote_id to display_id.

        Returns:
            Dict mapping remote IDs to display IDs
        """
        self._build_mappings()
        return self._remote_to_display.copy()

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        """
        Convert display IDs to remote IDs for database queries.

        Args:
            display_ids: List of display IDs

        Returns:
            List of corresponding remote IDs
        """
        self._build_mappings()
        return [self._display_to_remote.get(did.upper(), did.upper()) for did in display_ids]

    def to_display_id(self, remote_id: str) -> str:
        """
        Convert a remote_id to display_id.

        Args:
            remote_id: Remote ID from database

        Returns:
            Display ID for UI
        """
        self._build_mappings()
        return self._remote_to_display.get(remote_id.upper(), remote_id.upper())

    def to_remote_id(self, display_id: str) -> str:
        """
        Convert a display_id to remote_id.

        Args:
            display_id: Display ID from UI

        Returns:
            Remote ID for database
        """
        self._build_mappings()
        return self._display_to_remote.get(display_id.upper(), display_id.upper())

    def has_mapping(self, device_id: str) -> bool:
        """
        Check if a device has ID mapping configured.

        Args:
            device_id: Display or remote device ID

        Returns:
            True if device has different display/remote IDs
        """
        self._build_mappings()
        upper_id = device_id.upper()

        if upper_id in self._display_to_remote:
            return self._display_to_remote[upper_id] != upper_id
        if upper_id in self._remote_to_display:
            return self._remote_to_display[upper_id] != upper_id
        return False


__all__ = [
    "DeviceFileAdapter",
    "DeviceInfo",
    "CacheStats",
]
