# src/iFactory/infrastructure/configuration/settings.py
"""
Infrastructure: Application Settings Manager - Enhanced with Pydantic v2.

Features:
- Pydantic v2 validation with strict types
- Hierarchical settings with dot notation
- Thread-safe singleton with proper locking
- Qt integration with debounced saves
- Automatic backup and recovery
- Schema migration support
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from threading import RLock
from typing import (
    Annotated,
    Any,
    ClassVar,
    Final,
    Iterator,
    Literal,
    Optional,
    Self,
    TypeVar,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

try:
    from PySide6.QtCore import QObject, Signal, QTimer

    HAS_QT = True
except ImportError:
    HAS_QT = False

    # Mocks for non-Qt environments
    class QObject:  # type: ignore[no-redef]
        pass

    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args: Any) -> None:
            pass

        def emit(self, *args: Any) -> None:
            pass

        def connect(self, func: Any) -> None:
            pass

    class QTimer:  # type: ignore[no-redef]
        def __init__(self, parent: Any = None) -> None:
            self.timeout = Signal()

        def setSingleShot(self, val: bool) -> None:
            pass

        def start(self, ms: int) -> None:
            pass


from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

SCHEMA_VERSION: Final[str] = "2.0"
DEBOUNCE_DELAY_MS: Final[int] = 500
MAX_BACKUP_COUNT: Final[int] = 3


# ============================================================================
# Enums
# ============================================================================


class ThemeMode(StrEnum):
    """Supported UI themes."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class LogLevel(StrEnum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ============================================================================
# Settings Models (Pydantic v2)
# ============================================================================


class AppSettings(BaseModel):
    """Application-level settings with validation."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="ignore",
        str_strip_whitespace=True,
    )

    profile: str = Field(
        default="Equipment Realtime Visualization",
        min_length=1,
        max_length=100,
        description="Application profile name",
    )

    poll_fast_ms: PositiveInt = Field(
        default=3000,
        ge=1000,
        le=60000,
        alias="refresh_fast_ms",
        description="Fast polling interval in milliseconds",
    )

    poll_slow_ms: PositiveInt = Field(
        default=5000,
        ge=1000,
        le=300000,
        alias="refresh_slow_ms",
        description="Slow polling interval in milliseconds",
    )

    max_history_days: PositiveInt = Field(
        default=7,
        ge=1,
        le=365,
        description="Maximum days of history to retain",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level",
    )

    @model_validator(mode="after")
    def validate_poll_intervals(self) -> Self:
        """Ensure slow polling is >= fast polling."""
        if self.poll_slow_ms < self.poll_fast_ms:
            self.poll_slow_ms = self.poll_fast_ms
        return self


class UISettings(BaseModel):
    """UI-related settings with validation."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="ignore",
    )

    left_menu_collapsed: bool = Field(
        default=False,
        description="Whether left sidebar is collapsed",
    )

    show_device_labels: bool = Field(
        default=True,
        description="Show device labels on canvas",
    )

    gantt_show_axis: bool = Field(
        default=True,
        description="Show axis on Gantt chart",
    )

    animation_enabled: bool = Field(
        default=True,
        description="Enable UI animations",
    )

    tooltip_delay_ms: PositiveInt = Field(
        default=500,
        ge=0,
        le=5000,
        description="Tooltip delay in milliseconds",
    )


class DatabaseSettings(BaseModel):
    """Database connection settings (read from config, not .env for display)."""

    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        extra="ignore",
    )

    echo: bool = Field(default=False)
    pool_size: PositiveInt = Field(default=20, ge=1, le=100)
    max_overflow: PositiveInt = Field(default=40, ge=0, le=200)

    # MSSQL settings (for display only, actual creds from env)
    mssql_host: Optional[str] = Field(default=None)
    mssql_db: Optional[str] = Field(default=None)
    mssql_driver: str = Field(default="SQL Server")


class RootSettings(BaseModel):
    """Root settings model with all nested settings."""

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="allow",  # Allow extra fields for forward compatibility
        populate_by_name=True,
    )

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        alias="_schema_version",
    )

    theme: ThemeMode = Field(default=ThemeMode.LIGHT)

    right_panel_width: PositiveInt = Field(
        default=350,
        ge=200,
        le=1200,
    )

    default_page: str = Field(
        default="dashboard_page",
        pattern=r"^[a-z_]+$",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    ui: UISettings = Field(default_factory=UISettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)

    @field_validator("theme", mode="before")
    @classmethod
    def normalize_theme(cls, v: Any) -> ThemeMode:
        if isinstance(v, str):
            try:
                return ThemeMode(v.lower())
            except ValueError:
                return ThemeMode.LIGHT
        return v


# ============================================================================
# Settings Manager (Qt-integrated Singleton)
# ============================================================================

T = TypeVar("T")


class SettingsManager(QObject if HAS_QT else object):  # type: ignore[misc]
    """
    Thread-safe settings manager with Qt integration.

    Features:
    - Pydantic validation for all settings
    - Debounced auto-save
    - Automatic backup rotation
    - Schema migration support
    - Dot notation access (e.g., "app.poll_fast_ms")

    Usage:
        settings = SettingsManager()

        # Get with dot notation
        theme = settings.get("theme")
        poll_ms = settings.get("app.poll_fast_ms", 3000)

        # Set with validation
        settings.set("theme", "dark")

        # Type-safe access
        app = settings.app_settings
        ui = settings.ui_settings
    """

    # Qt Signals (only if Qt is available)
    if HAS_QT:
        settings_changed = Signal(str, object)  # key, value
        theme_changed = Signal(str)
        save_completed = Signal()
        save_failed = Signal(str)

    # Singleton
    _instance: ClassVar[Optional[SettingsManager]] = None
    _lock: ClassVar[RLock] = RLock()

    def __new__(cls, config_path: Optional[Path] = None) -> SettingsManager:
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if getattr(self, "_initialized", False):
            return

        if HAS_QT:
            super().__init__()

        self._path = config_path or PATHS.settings_path
        self._backup_dir = self._path.parent / "backups"
        self._rlock = RLock()
        self._settings: RootSettings = RootSettings()
        self._dirty = False
        self._loading = False

        # Qt timer for debounced saves
        if HAS_QT:
            self._save_timer = QTimer(self)
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._perform_save)
        else:
            self._save_timer = None

        self._load()
        self._initialized = True

    # ========================================================================
    # Loading & Saving
    # ========================================================================

    def _load(self) -> None:
        """Load settings from file with fallback chain."""
        with self._rlock:
            if self._loading:
                return
            self._loading = True

            try:
                loaded = False

                # Try main file
                if self._path.exists():
                    loaded = self._try_load_file(self._path)

                # Try backup if main failed
                if not loaded:
                    for backup in self._get_backup_files():
                        if self._try_load_file(backup):
                            logger.warning(f"Loaded from backup: {backup}")
                            loaded = True
                            break

                # Use defaults if all failed
                if not loaded:
                    logger.info("Using default settings")
                    self._settings = RootSettings()

            finally:
                self._loading = False

    def _try_load_file(self, path: Path) -> bool:
        """Attempt to load and validate settings from a file."""
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)

            # Handle schema migration
            data = self._migrate_schema(data)

            self._settings = RootSettings.model_validate(data)
            logger.info(f"Settings loaded from {path}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")

        return False

    def _migrate_schema(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate settings from older schema versions."""
        version = data.get("_schema_version", "1.0")

        if version == SCHEMA_VERSION:
            return data

        logger.info(f"Migrating settings from v{version} to v{SCHEMA_VERSION}")

        # Migration from 1.0 to 2.0
        if version == "1.0":
            # Rename fields
            if "app" in data:
                app = data["app"]
                if "poll_fast_ms" in app:
                    app["refresh_fast_ms"] = app.pop("poll_fast_ms")
                if "poll_slow_ms" in app:
                    app["refresh_slow_ms"] = app.pop("poll_slow_ms")

            data["_schema_version"] = SCHEMA_VERSION

        return data

    def _perform_save(self) -> None:
        """Actually save settings to disk."""
        with self._rlock:
            if not self._dirty:
                return

            try:
                # Create backup before saving
                self._create_backup()

                # Write to temp file first
                temp_path = self._path.with_suffix(".tmp")
                content = self._settings.model_dump_json(
                    indent=2,
                    by_alias=True,
                    exclude_none=True,
                )
                temp_path.write_text(content, encoding="utf-8")

                # Atomic rename
                temp_path.replace(self._path)

                self._dirty = False
                logger.debug("Settings saved successfully")

                if HAS_QT:
                    self.save_completed.emit()

            except Exception as e:
                logger.error(f"Failed to save settings: {e}")
                if HAS_QT:
                    self.save_failed.emit(str(e))

    def _create_backup(self) -> None:
        """Create a backup of current settings."""
        if not self._path.exists():
            return

        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._backup_dir / f"settings_{timestamp}.json"

            import shutil

            shutil.copy2(self._path, backup_path)

            # Rotate old backups
            self._rotate_backups()

        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def _rotate_backups(self) -> None:
        """Keep only the most recent backups."""
        backups = sorted(self._get_backup_files(), reverse=True)

        for old_backup in backups[MAX_BACKUP_COUNT:]:
            try:
                old_backup.unlink()
            except Exception:
                pass

    def _get_backup_files(self) -> list[Path]:
        """Get list of backup files sorted by modification time."""
        if not self._backup_dir.exists():
            return []

        return sorted(
            self._backup_dir.glob("settings_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _schedule_save(self) -> None:
        """Schedule a debounced save."""
        if self._save_timer and HAS_QT:
            self._save_timer.start(DEBOUNCE_DELAY_MS)
        else:
            self._perform_save()

    # ========================================================================
    # Public API
    # ========================================================================

    def get(self, key: str, default: T = None) -> T | Any:
        """
        Get a setting value using dot notation.

        Args:
            key: Dot-separated path (e.g., "app.poll_fast_ms")
            default: Default value if not found

        Returns:
            Setting value or default
        """
        with self._rlock:
            try:
                value: Any = self._settings
                for part in key.split("."):
                    if hasattr(value, part):
                        value = getattr(value, part)
                    elif isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return default
                return value
            except Exception:
                return default

    def set(self, key: str, value: Any, *, immediate: bool = False) -> bool:
        """
        Set a setting value with validation.

        Args:
            key: Dot-separated path
            value: New value (will be validated)
            immediate: Save immediately without debounce

        Returns:
            True if value was changed
        """
        with self._rlock:
            parts = key.split(".")

            try:
                # Navigate to parent
                target: Any = self._settings
                for part in parts[:-1]:
                    target = getattr(target, part)

                final_key = parts[-1]
                old_value = getattr(target, final_key, None)

                if old_value == value:
                    return False

                # Set with Pydantic validation
                setattr(target, final_key, value)
                self._dirty = True

                # Emit signals
                if not self._loading and HAS_QT:
                    self.settings_changed.emit(key, value)
                    if key == "theme":
                        self.theme_changed.emit(str(value))

                # Save
                if immediate:
                    self._perform_save()
                else:
                    self._schedule_save()

                return True

            except Exception as e:
                logger.error(f"Failed to set {key}={value}: {e}")
                return False

    def save(self) -> None:
        """Force immediate save."""
        self._dirty = True
        self._perform_save()

    def reload(self) -> None:
        """Reload settings from disk."""
        self._load()

    @contextmanager
    def batch_update(self) -> Iterator[None]:
        """
        Context manager for batch updates.

        Defers saving until all updates are complete.

        Usage:
            with settings.batch_update():
                settings.set("theme", "dark")
                settings.set("app.poll_fast_ms", 5000)
            # Single save happens here
        """
        with self._rlock:
            old_timer = self._save_timer
            self._save_timer = None
            try:
                yield
            finally:
                self._save_timer = old_timer
                if self._dirty:
                    self._schedule_save()

    # ========================================================================
    # Type-Safe Properties
    # ========================================================================

    @property
    def theme(self) -> ThemeMode:
        """Current theme mode."""
        return self._settings.theme

    @theme.setter
    def theme(self, value: ThemeMode | str) -> None:
        self.set("theme", value)

    @property
    def app_settings(self) -> AppSettings:
        """Application settings."""
        return self._settings.app

    @property
    def ui_settings(self) -> UISettings:
        """UI settings."""
        return self._settings.ui

    @property
    def db_settings(self) -> DatabaseSettings:
        """Database settings (read-only display)."""
        return self._settings.db

    @property
    def right_panel_width(self) -> int:
        """Right panel width."""
        return self._settings.right_panel_width

    @right_panel_width.setter
    def right_panel_width(self, value: int) -> None:
        self.set("right_panel_width", value)

    # ========================================================================
    # Device Configuration (Delegates to DeviceFileAdapter)
    # ========================================================================

    @cached_property
    def _device_adapter(self) -> Any:
        """Lazy-loaded device file adapter."""
        try:
            from iFactory.infrastructure.adapters.device_file_adapter import (
                DeviceFileAdapter,
            )

            return DeviceFileAdapter()
        except ImportError:
            return None

    def get_page_devices(self, page: str) -> list[str]:
        """Get device IDs for a page."""
        if self._device_adapter:
            return self._device_adapter.get_page_devices(page)
        return []

    def get_all_page_devices(self) -> dict[str, list[str]]:
        """Get all page device mappings."""
        if self._device_adapter:
            return self._device_adapter.get_all_page_devices()
        return {}

    def get_device_info(self, device_id: str) -> Optional[dict[str, Any]]:
        """Get device information."""
        if self._device_adapter:
            return self._device_adapter.get_device_info(device_id)
        return None

    # ========================================================================
    # Cleanup
    # ========================================================================

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                instance = cls._instance
                if hasattr(instance, "_save_timer") and instance._save_timer:
                    instance._save_timer.stop()
                cls._instance = None


# ============================================================================
# Module-level convenience function
# ============================================================================


def get_settings() -> SettingsManager:
    """Get the settings manager singleton."""
    return SettingsManager()


__all__ = [
    "SettingsManager",
    "get_settings",
    "AppSettings",
    "UISettings",
    "DatabaseSettings",
    "RootSettings",
    "ThemeMode",
    "LogLevel",
]
