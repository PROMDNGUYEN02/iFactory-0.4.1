"""
Application paths and constants.

Provides centralized path management and static configuration values.
All paths are resolved at import time and cached for performance.
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final, Optional
__all__ = ['PATHS', 'AppPaths', 'PROJECT_ROOT', 'PACKAGE_ROOT', 'DATA_DIR', 'THEME_BASE_PATH', 'THEME_VARS_PATH', 'APP_TITLE', 'APP_VERSION', 'APP_NAME', 'QtIcons', 'APP_ICON_PATH', 'ICON_LOGO', 'ICON_OPEN', 'ICON_CLOSE', 'ICON_SETTINGS', 'ICON_EXPAND', 'ICON_ARROW_OPEN', 'ICON_ARROW_CLOSE', 'MenuItem', 'MenuItems', 'DatabaseConfig', 'MSSQL_DRIVERS', 'detect_available_mssql_driver', 'Settings']
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _get_project_root() -> Path:
    """Get project root directory (cached)."""
    return Path(__file__).resolve().parents[3]

@lru_cache(maxsize=1)
def _get_package_root() -> Path:
    """Get package root directory (cached)."""
    return Path(__file__).resolve().parents[1]

class AppPaths:
    """
    Centralized path management.
    
    All paths are lazily computed and cached. Thread-safe singleton
    pattern ensures consistent paths across the application.
    
    Example:
        >>> from iFactory.config import PATHS
        >>> db_path = PATHS.hot_db_path
        >>> PATHS.ensure_directories()
    """
    _instance: Optional['AppPaths'] = None

    def __new__(cls) -> 'AppPaths':
        """Singleton pattern."""
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._project = _get_project_root()
            instance._package = _get_package_root()
            cls._instance = instance
        return cls._instance

    @property
    def project_root(self) -> Path:
        """Project root directory."""
        return self._project

    @property
    def package_root(self) -> Path:
        """Package root (src/iFactory)."""
        return self._package

    @property
    def data_dir(self) -> Path:
        """Data directory for persistent storage."""
        return self._project / 'data'

    @property
    def storage_dir(self) -> Path:
        """Storage directory for generated files."""
        return self.data_dir / 'storage_data'

    @property
    def settings_path(self) -> Path:
        """Settings JSON file path."""
        return self.data_dir / 'settings.json'

    @property
    def device_positions_path(self) -> Path:
        """Device positions JSON file path."""
        return self.data_dir / 'device_positions.json'

    @property
    def legends_path(self) -> Path:
        """Legends JSON file path."""
        return self.data_dir / 'legends.json'

    @property
    def hot_db_path(self) -> Path:
        """Hot storage SQLite database path."""
        return self.data_dir / 'hot_store.db'

    @property
    def cold_db_path(self) -> Path:
        """Cold storage SQLite database path."""
        return self.data_dir / 'cold_store.db'

    @property
    def resources_dir(self) -> Path:
        """Resources directory path."""
        return self._package / 'resources'

    @property
    def themes_dir(self) -> Path:
        """Themes directory path."""
        return self.resources_dir / 'themes'

    @property
    def theme_base_path(self) -> Path:
        """Base QSS theme file path."""
        return self.themes_dir / 'base.qss'

    @property
    def theme_vars_path(self) -> Path:
        """Theme variables JSON file path."""
        return self.themes_dir / 'variables.json'

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        directories = [self.data_dir, self.storage_dir]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def validate(self) -> dict[str, bool]:
        """
        Validate critical path existence.
        
        Returns:
            Dictionary mapping path names to existence status
        """
        return {'data_dir': self.data_dir.exists(), 'storage_dir': self.storage_dir.exists(), 'settings': self.settings_path.exists(), 'theme_base': self.theme_base_path.exists()}
PATHS: Final[AppPaths] = AppPaths()
PROJECT_ROOT: Final[Path] = PATHS.project_root
PACKAGE_ROOT: Final[Path] = PATHS.package_root
DATA_DIR: Final[Path] = PATHS.data_dir
THEME_BASE_PATH: Final[Path] = PATHS.theme_base_path
THEME_VARS_PATH: Final[Path] = PATHS.theme_vars_path
APP_NAME: Final[str] = 'iFactory'
APP_VERSION: Final[str] = '0.5.0'
APP_TITLE: Final[str] = 'AES Lithium Battery - Powering the Future  |  Designed by Industrial Engineering Team'

class QtIcons:
    """
    Qt resource system icon paths.
    
    All paths use the Qt resource system (:/prefix).
    Use `get_white_variant()` for dark theme icons.
    
    Example:
        >>> icon_path = QtIcons.DASHBOARD
        >>> white_icon = QtIcons.get_white_variant(icon_path)
    """
    __slots__ = ()
    APP: Final[str] = ':/icon/icon.ico'
    LOGO: Final[str] = ':/icon/logo.png'
    OPEN: Final[str] = ':/icon/open.svg'
    CLOSE: Final[str] = ':/icon/close.svg'
    SETTINGS: Final[str] = ':/icon/settings.svg'
    EXPAND: Final[str] = ':/icon/expand.svg'
    ARROW_OPEN: Final[str] = ':/icon/arrow_menu_open.svg'
    ARROW_CLOSE: Final[str] = ':/icon/arrow_menu_close.svg'
    DASHBOARD: Final[str] = ':/icon/dashboard.svg'
    ORDERS: Final[str] = ':/icon/orders.svg'
    PRODUCTS: Final[str] = ':/icon/products.svg'
    CUSTOMERS: Final[str] = ':/icon/customers.svg'
    REPORTS: Final[str] = ':/icon/reports.svg'

    @staticmethod
    def get_white_variant(path: str) -> str:
        """
        Get white variant of an icon path for dark themes.
        
        Args:
            path: Original icon path
            
        Returns:
            White variant path (adds -white before extension)
        """
        if path.endswith('.svg'):
            return path.replace('.svg', '-white.svg')
        return path
APP_ICON_PATH: Final[str] = QtIcons.APP
ICON_LOGO: Final[str] = QtIcons.LOGO
ICON_OPEN: Final[str] = QtIcons.OPEN
ICON_CLOSE: Final[str] = QtIcons.CLOSE
ICON_SETTINGS: Final[str] = QtIcons.SETTINGS
ICON_EXPAND: Final[str] = QtIcons.EXPAND
ICON_ARROW_OPEN: Final[str] = QtIcons.ARROW_OPEN
ICON_ARROW_CLOSE: Final[str] = QtIcons.ARROW_CLOSE

@dataclass(frozen=True, slots=True)
class MenuItem:
    """
    Menu item configuration.
    
    Attributes:
        title: Display title
        icon: Icon resource path
        shortcut: Keyboard shortcut
        tooltip: Hover tooltip text
    """
    title: str
    icon: str
    shortcut: str = ''
    tooltip: str = ''

    @property
    def icon_white(self) -> str:
        """Get white icon variant for dark themes."""
        return QtIcons.get_white_variant(self.icon)

class MenuItems:
    """
    Predefined menu items for application navigation.
    
    Example:
        >>> for item in MenuItems.all():
        ...     print(item.title, item.shortcut)
    """
    __slots__ = ()
    DASHBOARD: Final[MenuItem] = MenuItem('Dashboard', QtIcons.DASHBOARD, 'Ctrl+1')
    ORDERS: Final[MenuItem] = MenuItem('Orders', QtIcons.ORDERS, 'Ctrl+2')
    PRODUCTS: Final[MenuItem] = MenuItem('Products', QtIcons.PRODUCTS, 'Ctrl+3')
    CUSTOMERS: Final[MenuItem] = MenuItem('Customers', QtIcons.CUSTOMERS, 'Ctrl+4')
    REPORTS: Final[MenuItem] = MenuItem('Reports', QtIcons.REPORTS, 'Ctrl+5')
    SETTINGS: Final[MenuItem] = MenuItem('Settings', QtIcons.SETTINGS, 'Ctrl+,')

    @classmethod
    def all(cls) -> tuple[MenuItem, ...]:
        """Get all menu items in display order."""
        return (cls.DASHBOARD, cls.ORDERS, cls.PRODUCTS, cls.CUSTOMERS, cls.REPORTS, cls.SETTINGS)
MSSQL_DRIVERS: Final[tuple[str, ...]] = ('SQL Server', 'ODBC Driver 17 for SQL Server', 'ODBC Driver 18 for SQL Server')
DEFAULT_MSSQL_DRIVER: Final[str] = 'SQL Server'

@lru_cache(maxsize=1)
def detect_available_mssql_driver() -> str:
    """
    Detect best available MSSQL ODBC driver on system.
    
    Checks for installed drivers in order of preference:
    1. ODBC Driver 18 for SQL Server (latest)
    2. ODBC Driver 17 for SQL Server (modern)
    3. SQL Server (legacy, most compatible)
    
    Returns:
        Best available driver name, defaults to "SQL Server"
        
    Example:
        >>> driver = detect_available_mssql_driver()
        >>> print(f"Using driver: {driver}")
    """
    preferred_drivers = ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server', 'SQL Server']
    try:
        import pyodbc
        available = [d for d in pyodbc.drivers() if 'SQL Server' in d]
        for driver in preferred_drivers:
            if driver in available:
                logger.debug(f'Detected MSSQL driver: {driver}')
                return driver
        if available:
            logger.debug(f'Using available driver: {available[0]}')
            return available[0]
    except ImportError:
        logger.debug('pyodbc not installed, using default driver')
    except Exception as e:
        logger.warning(f'Error detecting MSSQL driver: {e}')
    return DEFAULT_MSSQL_DRIVER

@dataclass
class DatabaseConfig:
    """
    Database configuration for SQLite and MSSQL connections.
    
    Supports:
        - SQLite for local hot/cold storage
        - MSSQL for external data source
    
    Note:
        Default MSSQL driver is "SQL Server" for maximum compatibility.
        Use `detect_available_mssql_driver()` for auto-detection.
    
    Example:
        >>> config = DatabaseConfig(
        ...     mssql_host="localhost",
        ...     mssql_database="production",
        ...     mssql_user="app_user",
        ... )
        >>> print(config.mssql_url)
    """
    base_dir: Path = field(default_factory=lambda : PATHS.data_dir)
    hot_db_name: str = 'hot_store.db'
    cold_db_name: str = 'cold_store.db'
    mssql_host: Optional[str] = None
    mssql_database: Optional[str] = None
    mssql_user: Optional[str] = None
    mssql_password: Optional[str] = field(default=None, repr=False)
    mssql_driver: str = DEFAULT_MSSQL_DRIVER
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    pool_recycle: int = 1800

    @property
    def hot_db_path(self) -> Path:
        """Hot storage database path."""
        return self.base_dir / self.hot_db_name

    @property
    def cold_db_path(self) -> Path:
        """Cold storage database path."""
        return self.base_dir / self.cold_db_name

    @property
    def hot_db_url(self) -> str:
        """SQLAlchemy URL for hot storage."""
        return f'sqlite:///{self.hot_db_path}'

    @property
    def cold_db_url(self) -> str:
        """SQLAlchemy URL for cold storage."""
        return f'sqlite:///{self.cold_db_path}'

    @property
    def mssql_url(self) -> Optional[str]:
        """
        MSSQL connection URL for SQLAlchemy.
        
        Returns:
            Connection string or None if not configured
        """
        if not self.is_mssql_configured:
            return None
        user = self.mssql_user or os.getenv('MSSQL_USER', '')
        password = self.mssql_password or os.getenv('MSSQL_PASSWORD', '')
        driver_encoded = self.mssql_driver.replace(' ', '+')
        return f'mssql+pyodbc://{user}:{password}@{self.mssql_host}/{self.mssql_database}?driver={driver_encoded}'

    @property
    def is_mssql_configured(self) -> bool:
        """Check if MSSQL connection is properly configured."""
        return bool(self.mssql_host and self.mssql_database)

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """
        Create configuration from environment variables.
        
        Environment variables:
            - MSSQL_HOST: Server hostname
            - MSSQL_DATABASE: Database name
            - MSSQL_USER: Username
            - MSSQL_PASSWORD: Password
            - MSSQL_DRIVER: ODBC driver (optional)
        
        Returns:
            DatabaseConfig instance
        """
        return cls(mssql_host=os.getenv('MSSQL_HOST'), mssql_database=os.getenv('MSSQL_DATABASE'), mssql_user=os.getenv('MSSQL_USER'), mssql_password=os.getenv('MSSQL_PASSWORD'), mssql_driver=os.getenv('MSSQL_DRIVER', DEFAULT_MSSQL_DRIVER))

    @classmethod
    def with_auto_driver(cls, **kwargs) -> 'DatabaseConfig':
        """
        Create configuration with auto-detected MSSQL driver.
        
        Args:
            **kwargs: Other DatabaseConfig parameters
            
        Returns:
            DatabaseConfig with detected driver
        """
        if 'mssql_driver' not in kwargs:
            kwargs['mssql_driver'] = detect_available_mssql_driver()
        return cls(**kwargs)
Settings = AppPaths

@dataclass
class Settings:
    """Application settings container."""
    theme: str = 'light'
    language: str = 'en'