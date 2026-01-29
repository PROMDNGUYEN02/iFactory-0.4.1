"""
Theme Manager - Centralized logic for application styling.
Follows Singleton pattern to provide unified access to theme resources.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._current_theme = "light"
        self._variables: Dict[str, Any] = {}

        # Tự động tìm file variables.json cùng thư mục
        self._base_path = Path(__file__).parent
        self._load_variables()
        self._initialized = True

    def _load_variables(self):
        json_path = self._base_path / "variables.json"
        try:
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    self._variables = json.load(f)
            else:
                logger.warning(f"Theme variables not found at {json_path}")
                # Fallback data
                self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}
        except Exception as e:
            logger.error(f"Failed to load theme variables: {e}")
            self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}

    def set_theme(self, theme_name: str):
        if theme_name in ["light", "dark"]:
            self._current_theme = theme_name

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def get_color(self, key: str) -> str:
        """Get hex color string from current theme variables."""
        theme_vars = self._variables.get(self._current_theme, {})
        common_vars = self._variables.get("common", {})
        # Fallback: Theme var -> Common var -> Default Error Pink
        return theme_vars.get(key, common_vars.get(key, "#FF00FF"))

    def get_qcolor(self, key: str) -> QColor:
        return QColor(self.get_color(key))

    def get_icon_path(self, original_path: str) -> str:
        alias_map = self._variables.get("iconAlias", {}).get(self._current_theme, {})
        return alias_map.get(original_path, original_path)

    def get_stylesheet(self) -> str:
        qss_path = self._base_path / "base.qss"
        try:
            if not qss_path.exists():
                return ""
            with open(qss_path, "r", encoding="utf-8") as f:
                qss_template = f.read()

            # Merge variables
            replacements = {**self._variables.get("common", {}), **self._variables.get(self._current_theme, {})}

            # Replace placeholders
            for key, value in replacements.items():
                qss_template = qss_template.replace(f"${{{key}}}", str(value))

            return qss_template
        except Exception:
            return ""


# Global instance
theme_manager = ThemeManager()
