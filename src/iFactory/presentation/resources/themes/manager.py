# File: presentation/resources/themes/manager.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class ThemeManager:
    _instance: ThemeManager = None

    def __new__(cls) -> ThemeManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._current_theme = "light"
        self._variables: Dict[str, Any] = {}
        self._base_path = Path(__file__).parent
        self._load_variables()
        self._initialized = True

    def _load_variables(self) -> None:
        json_path = self._base_path / "variables.json"
        try:
            if json_path.exists():
                self._variables = json.loads(json_path.read_text(encoding="utf-8"))
            else:
                logger.warning("Theme variables not found: %s", json_path)
                self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}
        except Exception as e:
            logger.error("Failed to load theme variables: %s", e)
            self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}

    def set_theme(self, theme: str) -> None:
        if theme in ("light", "dark"):
            self._current_theme = theme

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def get_color(self, key: str) -> str:
        theme_vars = self._variables.get(self._current_theme, {})
        common_vars = self._variables.get("common", {})
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

            template = qss_path.read_text(encoding="utf-8")
            replacements = {
                **self._variables.get("common", {}),
                **self._variables.get(self._current_theme, {}),
            }

            for key, value in replacements.items():
                template = template.replace(f"${{{key}}}", str(value))

            return template

        except Exception as e:
            logger.error("Failed to load stylesheet: %s", e)
            return ""


_theme_manager_instance: ThemeManager = None


def get_theme_manager() -> ThemeManager:
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance


theme_manager = get_theme_manager()


__all__ = ["ThemeManager", "get_theme_manager", "theme_manager"]
