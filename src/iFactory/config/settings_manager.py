"""
Settings Manager - Thread-safe settings with async persistence.

Features:
    - Thread-safe read/write operations.
    - Debounced auto-save (reduces disk I/O).
    - Type-safe dataclass integration.
    - Qt signal notifications.
    - Atomic file operations with backup.
    - Delegation of Device Config queries to DeviceConfigLoader.

Example:
    >>> settings = SettingsManager()
    >>> settings.set("theme", "dark")
    >>> theme = settings.theme
"""

from __future__ import annotations
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock, Lock
from typing import Any, ClassVar, Final, Optional
from PySide6.QtCore import QObject, Signal, QTimer

__all__ = ["SettingsManager", "DBSettings", "AppSettings", "UISettings"]
logger = logging.getLogger(__name__)
DEBOUNCE_DELAY_MS: Final[int] = 500
MAX_BACKUP_FILES: Final[int] = 3
SCHEMA_VERSION: Final[str] = "1.0"


@dataclass(slots=True)
class DBSettings:
    """
    Database connection settings.

    Attributes:
        mssql_dsn: ODBC connection string.
        mssql_host: SQL Server hostname.
        mssql_db: Database name.
        mssql_user: Username.
        mssql_password: Password (hidden in repr).
        mssql_driver: ODBC driver name (default: "SQL Server").
        echo: Enable SQL logging.
        pool_size: Connection pool size.
        max_overflow: Max overflow connections.
    """

    mssql_dsn: Optional[str] = None
    mssql_host: Optional[str] = None
    mssql_db: Optional[str] = None
    mssql_user: Optional[str] = None
    mssql_password: Optional[str] = field(default=None, repr=False)
    mssql_driver: str = "SQL Server"
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 40

    def __post_init__(self) -> None:
        """Validate settings."""
        if self.pool_size < 1:
            raise ValueError("pool_size must be >= 1")
        if self.max_overflow < 0:
            raise ValueError("max_overflow must be >= 0")

    @property
    def is_configured(self) -> bool:
        """Check if database is properly configured."""
        return bool(self.mssql_dsn or (self.mssql_host and self.mssql_db))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DBSettings":
        """Create from dictionary (filters unknown keys)."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for (k, v) in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_env(cls) -> "DBSettings":
        """
        Create from environment variables.

        Environment variables:
            - MSSQL_HOST
            - MSSQL_DATABASE
            - MSSQL_USER
            - MSSQL_PASSWORD
            - MSSQL_DRIVER (default: "SQL Server")
        """
        return cls(
            mssql_host=os.getenv("MSSQL_HOST"),
            mssql_db=os.getenv("MSSQL_DATABASE"),
            mssql_user=os.getenv("MSSQL_USER"),
            mssql_password=os.getenv("MSSQL_PASSWORD"),
            mssql_driver=os.getenv("MSSQL_DRIVER", "SQL Server"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass(slots=True)
class AppSettings:
    """Application-level settings."""

    profile: str = "Equipment Realtime Visualization"
    refresh_fast_ms: int = 3000
    refresh_slow_ms: int = 5000
    max_history_days: int = 7

    def __post_init__(self) -> None:
        """Validate and normalize settings."""
        self.refresh_fast_ms = max(1000, self.refresh_fast_ms)
        self.refresh_slow_ms = max(self.refresh_fast_ms, self.refresh_slow_ms)
        self.max_history_days = max(1, self.max_history_days)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """Create from dictionary."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for (k, v) in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass(slots=True)
class UISettings:
    """UI-related settings."""

    theme: str = "light"
    right_panel_width: int = 800
    left_menu_collapsed: bool = False
    show_device_labels: bool = True
    gantt_show_axis: bool = True

    def __post_init__(self) -> None:
        """Validate and normalize settings."""
        if self.theme not in ("light", "dark"):
            self.theme = "light"
        self.right_panel_width = max(150, min(1200, self.right_panel_width))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UISettings":
        """Create from dictionary."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for (k, v) in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SettingsManager(QObject):
    """
    Thread-safe settings manager with debounced persistence.

    Implements Singleton pattern via `__new__` to avoid metaclass conflict
    with QObject (which has its own complex metaclass).

    Features:
        - Singleton behavior (only one instance).
        - Lazy loading from JSON file.
        - Thread-safe operations using instance-level RLock.
        - Debounced auto-save (500ms) to reduce disk I/O.
        - Type-safe dataclass integration (`DBSettings`, `AppSettings`, `UISettings`).
        - Qt Signal notifications (`settings_changed`, `theme_changed`, `save_completed`).
        - Atomic file operations with backup (.json.bak).
        - **Delegation of Device Config queries to DeviceConfigLoader**.
    """

    settings_changed = Signal(str, object)
    theme_changed = Signal(str)
    save_completed = Signal()
    save_failed = Signal(str)
    _instance: ClassVar[Optional["SettingsManager"]] = None
    _lock: ClassVar[Lock] = Lock()

    def __new__(
        cls,
        path: Optional[Path] = None,
        auto_save: bool = True,
        parent: Optional[QObject] = None,
    ) -> "SettingsManager":
        """
        Singleton behavior enforcement via __new__.

        Ensures that only one instance of `SettingsManager` exists.

        Returns:
            The singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        """
        Initialize settings manager.
        """
        if hasattr(self, "_initialized"):
            return
        super().__init__(*args, **kwargs)
        path = kwargs.get("path")
        auto_save = kwargs.get("auto_save", True)
        self._internal_init(path, auto_save)
        self._initialized = True

    def _internal_init(
        self, path: Optional[Path] = None, auto_save: bool = True
    ) -> None:
        """
        Internal initialization logic.

        Called only once during the first instantiation.
        """
        self._path = self._resolve_config_path(path)
        self._backup_path = self._path.with_suffix(".json.bak")
        self._auto_save = auto_save
        self._lock = RLock()
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._loading = False
        self._save_timer: Optional[QTimer] = None
        if self._auto_save:
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save_sync)
        self._load()

    def _resolve_config_path(self, path: Optional[Path]) -> Path:
        """Resolve settings file path."""
        if path:
            return Path(path)
        from .settings import PATHS

        return PATHS.settings_path

    def _load(self) -> None:
        """Load settings from disk."""
        with self._lock:
            if self._loading:
                return
            self._loading = True
            try:
                self._load_from_files()
            finally:
                self._loading = False

    def _load_from_files(self) -> None:
        """Try loading from main file, then backup."""
        for path in (self._path, self._backup_path):
            if self._try_load_file(path):
                return
        self._set_defaults()

    def _try_load_file(self, path: Path) -> bool:
        """Attempt to load settings from a file."""
        if not path.exists():
            return False
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            self._data = data
            logger.info(f"Settings loaded from {path}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to read {path}: {e}")
            return False

    def _set_defaults(self) -> None:
        """Reset all settings to default values."""
        from .constants import UIConstants, Limits

        self._data = {
            "_schema_version": SCHEMA_VERSION,
            "theme": "light",
            "right_panel_width": UIConstants.RIGHT_PANEL_WIDTH_EXPANDED,
            "app": {
                "profile": "Equipment Realtime Visualization",
                "refresh_fast_ms": Limits.POLL_FAST_MS,
                "refresh_slow_ms": Limits.POLL_SLOW_MS,
                "max_history_days": 7,
            },
            "ui": {
                "left_menu_collapsed": False,
                "show_device_labels": True,
                "gantt_show_axis": True,
            },
            "db": {
                "mssql_dsn": "",
                "mssql_host": "",
                "mssql_db": "",
                "mssql_user": "",
                "mssql_password": "",
                "mssql_driver": "SQL Server",
                "echo": False,
                "pool_size": 20,
                "max_overflow": 40,
            },
        }

    def _save_sync(self) -> None:
        """Synchronous save with atomic write."""
        with self._lock:
            if not self._dirty:
                return
            try:
                self._create_backup()
                self._atomic_write()
                self._dirty = False
                logger.debug("Settings saved")
                self.save_completed.emit()
            except Exception as e:
                logger.error(f"Save failed: {e}", exc_info=True)
                self.save_failed.emit(str(e))

    def _create_backup(self) -> None:
        """Create backup of current settings file."""
        if not self._path.exists():
            return
        try:
            self._path.replace(self._backup_path)
        except OSError as e:
            logger.warning(f"Backup failed: {e}")

    def _atomic_write(self) -> None:
        """Write settings atomically via temp file."""
        temp_path = self._path.with_suffix(".tmp")
        content = json.dumps(self._data, indent=2, ensure_ascii=False, sort_keys=True)
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(self._path)

    def _schedule_save(self) -> None:
        """Schedule a debounced save."""
        if self._auto_save and self._save_timer:
            self._save_timer.start(DEBOUNCE_DELAY_MS)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting by key (supports dot notation).

        Args:
            key: Setting key (e.g., "theme" or "app.refresh_fast_ms").
            default: Default value if not found.

        Returns:
            Setting value.
        """
        with self._lock:
            keys = key.split(".")
            value = self._data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value: Any, *, immediate: bool = False) -> None:
        """
        Set setting by key (supports dot notation).

        Args:
            key: Setting key.
            value: New value.
            immediate: Force immediate save (bypasses debounce).
        """
        with self._lock:
            keys = key.split(".")
            data = self._data
            for k in keys[:-1]:
                if k not in data or not isinstance(data[k], dict):
                    data[k] = {}
                data = data[k]
            final_key = keys[-1]
            old_value = data.get(final_key)
            if old_value != value:
                data[final_key] = value
                self._dirty = True
                if not self._loading:
                    self.settings_changed.emit(key, value)
                    if key == "theme":
                        self.theme_changed.emit(str(value))
                if immediate:
                    self._save_sync()
                else:
                    self._schedule_save()

    @property
    def theme(self) -> str:
        """Current theme mode."""
        return self.get("theme", "light")

    @theme.setter
    def theme(self, mode: str) -> None:
        """Set theme mode."""
        self.set("theme", "dark" if mode == "dark" else "light")

    @property
    def default_page(self) -> str:
        """Get default page."""
        return self._data.get("default_page", "orders_page")

    @default_page.setter
    def default_page(self, value: str) -> None:
        """Set default page."""
        self.set("default_page", value)

    @property
    def right_panel_width(self) -> int:
        """Right panel width."""
        return self.get("right_panel_width", 800)

    @right_panel_width.setter
    def right_panel_width(self, value: int) -> None:
        """Set right panel width (clamped 150-1200)."""
        self.set("right_panel_width", max(150, min(1200, value)))

    @property
    def ui_settings(self) -> UISettings:
        """Get UI settings as dataclass."""
        data = {
            "theme": self.theme,
            "right_panel_width": self.right_panel_width,
            **self.get("ui", {}),
        }
        return UISettings.from_dict(data)

    @property
    def app_settings(self) -> AppSettings:
        """Get app settings as dataclass."""
        return AppSettings.from_dict(self.get("app", {}))

    @property
    def db_settings(self) -> DBSettings:
        """Get database settings as dataclass."""
        return DBSettings.from_dict(self.get("db", {}))

    @property
    def is_loaded(self) -> bool:
        """Check if configuration has been loaded."""
        return bool(self._data)

    def get_page_devices(self, page: str) -> list[str]:
        """
        Get device IDs for a specific page.

        Delegates to DeviceConfigLoader to ensure correct data source
        (device_positions.json) is used.

        Args:
            page: Page name (e.g., "dashboard_page").

        Returns:
            List of device IDs.
        """
        from .device_config import DeviceConfigLoader

        return DeviceConfigLoader().get_page_devices(page)

    def get_all_page_devices(self) -> dict[str, list[str]]:
        """
        Get complete page-to-devices mapping.

        Delegates to DeviceConfigLoader.

        Returns:
            Dictionary mapping page names to device ID lists.
        """
        from .device_config import DeviceConfigLoader

        return DeviceConfigLoader().get_all_page_devices()

    def get_device_info(self, device_id: str) -> Optional[dict]:
        """
        Get full device configuration by ID.

        Delegates to DeviceConfigLoader.

        Args:
            device_id: Device identifier.

        Returns:
            Device info dict or None if not found.
        """
        from .device_config import DeviceConfigLoader

        return DeviceConfigLoader().get_device_info(device_id)

    def save(self, *, force: bool = False) -> None:
        """
        Force save settings immediately.

        Args:
            force: Force save immediately even if not dirty.
        """
        if force:
            with self._lock:
                self._dirty = True
                self._save_sync()
        else:
            self._schedule_save()

    def reload(self) -> None:
        """Reload settings from disk."""
        with self._lock:
            self._dirty = False
            if self._save_timer:
                self._save_timer.stop()
        self._load()
        self.settings_changed.emit("*", None)

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        with self._lock:
            self._set_defaults()
            self._dirty = True
            self._save_sync()
        self.settings_changed.emit("*", None)

    def has_db_config(self) -> bool:
        """Check if database is configured."""
        return self.db_settings.is_configured

    def close(self) -> None:
        """
        Close manager and save pending changes.

        Stops the debounce timer and performs a final save.
        """
        if self._save_timer:
            self._save_timer.stop()
        with self._lock:
            if self._dirty:
                self._save_sync()
