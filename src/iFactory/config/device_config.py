"""
Device Configuration Loader - Thread-safe singleton for device configs.

Provides efficient loading and lookup of device configurations
from JSON files with lazy initialization and thread safety.
"""
from __future__ import annotations
import json
import logging
import threading
from pathlib import Path
from typing import ClassVar, Final, Optional
__all__ = ['DeviceConfigLoader', 'get_page_devices', 'get_all_page_devices']
logger = logging.getLogger(__name__)
_FRAME_TO_PAGE: Final[dict[str, str]] = {'daboard_midle_frame_1': 'daboard_page', 'daboard_midle_frame_2': 'daboard_page', 'orders_midle_frame_1': 'orders_page', 'orders_midle_frame_2': 'orders_page'}

class _Singleton(type):
    """
    Metaclass to implement a thread-safe Singleton pattern.
    Ensures that only one instance of `DeviceConfigLoader` exists.
    """
    _instances: ClassVar[dict[type, object]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args, **kwargs):
        """
        Get or create the singleton instance.

        Returns:
            The singleton instance.
        """
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class DeviceConfigLoader(metaclass=_Singleton):
    """
    Thread-safe singleton for device configuration management.

    Features:
        - Lazy loading from JSON file.
        - Thread-safe operations using locks.
        - Efficient caching of device lookups.
        - Page-to-devices and Device-to-Page mappings.
    """

    def __init__(self):
        """Initialize loader state."""
        self._state_lock = threading.RLock()
        self._config: dict = {}
        self._page_devices: dict[str, list[str]] = {}
        self._device_cache: dict[str, dict] = {}
        self._loaded: bool = False

    def load(self, path: Optional[Path]=None) -> bool:
        """
        Load device configuration from JSON file.

        Args:
            path: Custom config path (uses default if None).

        Returns:
            True if loaded successfully, False otherwise.
        """
        with self._state_lock:
            if self._loaded and path is None:
                return True
            config_path = self._resolve_config_path(path)
            if not self._validate_config_path(config_path):
                return False
            try:
                content = config_path.read_text(encoding='utf-8')
                self._config = json.loads(content)
                self._parse_devices()
                self._loaded = True
                device_count = sum((len(d) for d in self._page_devices.values()))
                logger.info(f'Device config loaded: {len(self._page_devices)} pages, {device_count} devices')
                return True
            except json.JSONDecodeError as e:
                logger.error(f'Invalid JSON in device config: {e}')
                self._loaded = True
                raise ValueError(f'Invalid JSON in device config: {e}') from e
            except OSError as e:
                logger.error(f'Failed to read device config: {e}')
                raise FileNotFoundError(f'Device config file not found: {path}') from e

    def _resolve_config_path(self, path: Optional[Path]) -> Path:
        """Resolve configuration file path."""
        if path:
            return Path(path)
        from iFactory.config import PATHS
        return PATHS.device_positions_path

    def _validate_config_path(self, path: Path) -> bool:
        """Validate config file exists and is readable."""
        if path is None:
            logger.warning('Device config path is None')
            return False
        if not path.exists():
            logger.warning(f'Device config not found: {path}')
            return False
        if not path.is_file():
            logger.error(f'Device config is not a file: {path}')
            return False
        return True

    def _parse_devices(self) -> None:
        """Parse devices from config and build lookup tables."""
        self._page_devices.clear()
        self._device_cache.clear()
        for (frame_name, frame_config) in self._config.items():
            self._process_frame(frame_name, frame_config)
        for devices in self._page_devices.values():
            devices.sort()

    def _process_frame(self, frame_name: str, frame_config: dict) -> None:
        """Process a single frame configuration."""
        page_name = self._get_page_name(frame_name)
        if not page_name:
            return
        if page_name not in self._page_devices:
            self._page_devices[page_name] = []
        devices = frame_config.get('devices', [])
        for device in devices:
            self._process_device(device, page_name)

    def _process_device(self, device: dict, page_name: str) -> None:
        """Process and cache a single device entry."""
        device_id = device.get('id') or device.get('code')
        if not device_id:
            return
        page_list = self._page_devices[page_name]
        if device_id not in page_list:
            page_list.append(device_id)
        self._device_cache[device_id] = device.copy()

    def _get_page_name(self, frame_name: str) -> Optional[str]:
        """Extract page name from frame name using mapping table."""
        if frame_name in _FRAME_TO_PAGE:
            return _FRAME_TO_PAGE[frame_name]
        if '_midle_' in frame_name:
            prefix = frame_name.split('_midle_')[0]
            return f'{prefix}_page'
        return None

    def get_page_devices(self, page: str) -> list[str]:
        """Get device IDs for a specific page."""
        self._ensure_loaded()
        with self._state_lock:
            devices = self._page_devices.get(page, [])
            return devices.copy()

    def get_all_page_devices(self) -> dict[str, list[str]]:
        """Get complete page-to-devices mapping."""
        self._ensure_loaded()
        with self._state_lock:
            return {page: devices.copy() for (page, devices) in self._page_devices.items()}

    def get_device_info(self, device_id: str) -> Optional[dict]:
        """Get full device configuration by ID."""
        self._ensure_loaded()
        with self._state_lock:
            info = self._device_cache.get(device_id)
            return info.copy() if info else None

    def reload(self, path: Optional[Path]=None) -> bool:
        """Force reload configuration from disk."""
        with self._state_lock:
            self._loaded = False
            self._config.clear()
            self._page_devices.clear()
            self._device_cache.clear()
            return self.load(path)

    @property
    def is_loaded(self) -> bool:
        """Check if configuration has been loaded."""
        return self._loaded

    @property
    def total_devices(self) -> int:
        """Get total number of unique devices."""
        self._ensure_loaded()
        with self._state_lock:
            return len(self._device_cache)

    @property
    def page_count(self) -> int:
        """Get number of configured pages."""
        self._ensure_loaded()
        with self._state_lock:
            return len(self._page_devices)

    def _ensure_loaded(self) -> None:
        """Ensure configuration is loaded (lazy loading)."""
        if not self._loaded:
            self.load()

def get_page_devices(page: str) -> list[str]:
    """Get devices for a page."""
    return DeviceConfigLoader().get_page_devices(page)

def get_all_page_devices() -> dict[str, list[str]]:
    """Get all page-to-devices mappings."""
    return DeviceConfigLoader().get_all_page_devices()