"""
Infrastructure: Application Settings Manager.
Implements ISettingsManager using JSON persistence.
Adapts to Qt environment if available, otherwise runs pure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, Lock
from typing import Any, ClassVar, Final, Optional
from abc import ABCMeta

try:
    # Optional dependency: Adapter for Qt Environment
    from PySide6.QtCore import QObject, Signal, QTimer

    HAS_QT = True

    # Resolve Metaclass Conflict: Create a metaclass that inherits from both
    # QObject's metaclass (Shiboken.ObjectType) and ABCMeta.
    class QABCMeta(type(QObject), ABCMeta):
        pass

except ImportError:
    HAS_QT = False

    # Fallback mocks for pure python environment
    class QObject:
        pass

    class Signal:
        def __init__(self, *args):
            pass

        def emit(self, *args):
            pass

        def connect(self, func):
            pass

    class QTimer:
        def __init__(self, parent=None):
            self.timeout = Signal()

        def setSingleShot(self, val):
            pass

        def start(self, ms):
            pass

        def connect(self, func):
            pass

    # In pure Python, QObject is a standard class (type),
    # so ABCMeta is sufficient as the metaclass.
    QABCMeta = ABCMeta


from iFactory.application.ports.config import ISettingsManager
from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)

DEBOUNCE_DELAY_MS: Final[int] = 500
SCHEMA_VERSION: Final[str] = "1.0"
DEFAULT_RIGHT_PANEL_WIDTH: Final[int] = 350  # Default value isolated from Presentation layer


@dataclass(slots=True)
class AppSettings:
    """Application-level settings DTO."""

    profile: str = "Equipment Realtime Visualization"
    refresh_fast_ms: int = 3000
    refresh_slow_ms: int = 5000
    max_history_days: int = 7

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for (k, v) in data.items() if k in known}
        return cls(**filtered)


@dataclass(slots=True)
class UISettings:
    """UI-related settings DTO."""

    theme: str = "light"
    right_panel_width: int = 800
    left_menu_collapsed: bool = False
    show_device_labels: bool = True
    gantt_show_axis: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UISettings":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for (k, v) in data.items() if k in known}
        return cls(**filtered)


class SettingsManager(QObject, ISettingsManager, metaclass=QABCMeta):
    """
    Thread-safe settings manager.
    Acts as an adapter to the filesystem for persistence.
    Acts as an adapter to Qt (via QObject/Signal) for reactive UI updates.
    """

    settings_changed = Signal(str, object)
    theme_changed = Signal(str)
    save_completed = Signal()
    save_failed = Signal(str)

    _instance: ClassVar[Optional["SettingsManager"]] = None
    _lock: ClassVar[Lock] = Lock()

    def __new__(cls, *args, **kwargs) -> "SettingsManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        if hasattr(self, "_initialized"):
            return
        # Initialize QObject only if Qt is present
        if HAS_QT:
            super().__init__()
        else:
            super().__init__()

        self._internal_init()
        self._initialized = True

    def _internal_init(self) -> None:
        self._path = PATHS.settings_path
        self._backup_path = self._path.with_suffix(".json.bak")
        self._rlock = RLock()
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._loading = False

        if HAS_QT:
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._save_sync)
        else:
            # Simple fallback or no-op for timer in non-UI context
            self._save_timer = None

        self._load()

    def _load(self) -> None:
        with self._rlock:
            if self._loading:
                return
            self._loading = True
            try:
                if not self._try_load_file(self._path):
                    if not self._try_load_file(self._backup_path):
                        self._set_defaults()
            finally:
                self._loading = False

    def _try_load_file(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            content = path.read_text(encoding="utf-8")
            self._data = json.loads(content)
            logger.info(f"Settings loaded from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            return False

    def _set_defaults(self) -> None:
        self._data = {
            "_schema_version": SCHEMA_VERSION,
            "theme": "light",
            "right_panel_width": DEFAULT_RIGHT_PANEL_WIDTH,
            "app": {
                "profile": "Equipment Realtime Visualization",
                "refresh_fast_ms": 3000,
                "refresh_slow_ms": 5000,
                "max_history_days": 7,
            },
            "ui": {
                "left_menu_collapsed": False,
                "show_device_labels": True,
                "gantt_show_axis": True,
            },
        }

    def _save_sync(self) -> None:
        with self._rlock:
            if not self._dirty:
                return
            try:
                temp_path = self._path.with_suffix(".tmp")
                content = json.dumps(
                    self._data,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                temp_path.write_text(content, encoding="utf-8")
                temp_path.replace(self._path)
                self._dirty = False
                if HAS_QT:
                    self.save_completed.emit()
            except Exception as e:
                logger.error(f"Save failed: {e}")
                if HAS_QT:
                    self.save_failed.emit(str(e))

    def _schedule_save(self) -> None:
        if self._save_timer and HAS_QT:
            self._save_timer.start(DEBOUNCE_DELAY_MS)
        else:
            # Sync save in CLI/Test environment
            self._save_sync()

    # --- ISettingsManager Implementation ---

    def get(self, key: str, default: Any = None) -> Any:
        with self._rlock:
            keys = key.split(".")
            value = self._data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value: Any, immediate: bool = False) -> None:
        with self._rlock:
            keys = key.split(".")
            data = self._data
            for k in keys[:-1]:
                if k not in data or not isinstance(data[k], dict):
                    data[k] = {}
                data = data[k]

            final_key = keys[-1]
            if data.get(final_key) != value:
                data[final_key] = value
                self._dirty = True
                if not self._loading and HAS_QT:
                    self.settings_changed.emit(key, value)
                    if key == "theme":
                        self.theme_changed.emit(str(value))

                if immediate:
                    self._save_sync()
                else:
                    self._schedule_save()

    def save(self) -> None:
        self._save_sync()

    # --- Type-Safe Properties ---

    @property
    def theme(self) -> str:
        return self.get("theme", "light")

    @property
    def ui_settings(self) -> UISettings:
        data = {
            "theme": self.theme,
            "right_panel_width": self.get("right_panel_width", 800),
            **self.get("ui", {}),
        }
        return UISettings.from_dict(data)

    @property
    def app_settings(self) -> AppSettings:
        return AppSettings.from_dict(self.get("app", {}))

    # --- Adapter Methods for Device Config ---

    def get_page_devices(self, page: str) -> list[str]:
        try:
            from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter

            return DeviceFileAdapter().get_page_devices(page)
        except ImportError:
            return []

    def get_all_page_devices(self) -> dict[str, list[str]]:
        try:
            from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter

            return DeviceFileAdapter().get_all_page_devices()
        except ImportError:
            return {}

    def get_device_info(self, device_id: str) -> Optional[dict]:
        try:
            from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter

            return DeviceFileAdapter().get_device_info(device_id)
        except ImportError:
            return None
