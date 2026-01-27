"""
Infrastructure: JSON Settings Manager.
Implementation of Settings persistence using JSON files.
Refactored from original SettingsManager to fit Clean Architecture.
"""

from __future__ import annotations
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock, Lock
from typing import Any, ClassVar, Final, Optional
from PySide6.QtCore import QObject, Signal, QTimer

# [DDD Imports]
from iFactory.infrastructure.config.app_paths import PATHS
from iFactory.presentation.constants.ui_constants import UIConstants
from iFactory.domain.constants import ApplicationLimits as Limits

# [FIXED] Import từ file device_config.py mới tạo ở cùng thư mục
from .device_config import DeviceConfigLoader

logger = logging.getLogger(__name__)

DEBOUNCE_DELAY_MS: Final[int] = 500
SCHEMA_VERSION: Final[str] = "1.0"


@dataclass(slots=True)
class AppSettings:
    """Application-level settings."""

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
    """UI-related settings."""

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


class SettingsManager(QObject):
    """
    Thread-safe settings manager with debounced persistence.
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
        super().__init__()
        self._internal_init()
        self._initialized = True

    def _internal_init(self) -> None:
        self._path = PATHS.settings_path
        self._backup_path = self._path.with_suffix(".json.bak")
        self._lock = RLock()
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._loading = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_sync)

        self._load()

    def _load(self) -> None:
        with self._lock:
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
            "right_panel_width": UIConstants.RIGHT_PANEL_WIDTH_EXPANDED,
            "app": {
                "profile": "Equipment Realtime Visualization",
                "refresh_fast_ms": Limits.POLL_FAST_MS if hasattr(Limits, "POLL_FAST_MS") else 3000,
                "refresh_slow_ms": Limits.POLL_SLOW_MS if hasattr(Limits, "POLL_SLOW_MS") else 5000,
                "max_history_days": 7,
            },
            "ui": {
                "left_menu_collapsed": False,
                "show_device_labels": True,
                "gantt_show_axis": True,
            },
        }

    def _save_sync(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            try:
                temp_path = self._path.with_suffix(".tmp")
                content = json.dumps(self._data, indent=2, ensure_ascii=False, sort_keys=True)
                temp_path.write_text(content, encoding="utf-8")
                temp_path.replace(self._path)
                self._dirty = False
                self.save_completed.emit()
            except Exception as e:
                logger.error(f"Save failed: {e}")
                self.save_failed.emit(str(e))

    def _schedule_save(self) -> None:
        self._save_timer.start(DEBOUNCE_DELAY_MS)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            keys = key.split(".")
            value = self._data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
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
                if not self._loading:
                    self.settings_changed.emit(key, value)
                    if key == "theme":
                        self.theme_changed.emit(str(value))
                self._schedule_save()

    # --- Properties ---
    @property
    def theme(self) -> str:
        return self.get("theme", "light")

    @property
    def ui_settings(self) -> UISettings:
        data = {"theme": self.theme, "right_panel_width": self.get("right_panel_width", 800), **self.get("ui", {})}
        return UISettings.from_dict(data)

    @property
    def app_settings(self) -> AppSettings:
        return AppSettings.from_dict(self.get("app", {}))

    # --- Device Config Delegation ---
    # Các hàm này giúp UI lấy cấu hình thiết bị mà không cần gọi trực tiếp Infrastructure
    def get_page_devices(self, page: str) -> list[str]:
        return DeviceConfigLoader().get_page_devices(page)

    def get_all_page_devices(self) -> dict[str, list[str]]:
        return DeviceConfigLoader().get_all_page_devices()

    def get_device_info(self, device_id: str) -> Optional[dict]:
        return DeviceConfigLoader().get_device_info(device_id)
