# File: presentation/resources/themes/manager.py
"""
Theme Manager - Enhanced with modular QSS loading.

Provides backward compatibility while delegating to ThemeService.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)


class ThemeManager:
    """
    Theme Manager with modular QSS support.

    Delegates to ThemeService but can also work standalone.
    """

    _instance: Optional["ThemeManager"] = None

    # QSS files to load in order
    QSS_MODULES: List[str] = [
        "_global.qss",
        "_scrollbar.qss",
        "_buttons.qss",
        "_inputs.qss",
        "_panels.qss",
        "_cards.qss",
        "_status.qss",
        "_tooltips.qss",
    ]

    def __new__(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        from ...services.theme_service import get_theme_service

        self._theme_service = get_theme_service()
        self._base_path = Path(__file__).parent
        self._styles_path = self._base_path / "styles"
        self._initialized = True

    def set_theme(self, theme: str) -> None:
        """Set current theme."""
        self._theme_service.set_theme(theme)

    @property
    def current_theme(self) -> str:
        """Get current theme name."""
        return self._theme_service.current_theme

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    def get_color(self, key: str) -> str:
        """Get color by key."""
        return self._theme_service.get_color(key)

    def get_qcolor(self, key: str) -> QColor:
        """Get color as QColor."""
        return self._theme_service.get_qcolor(key)

    def get_icon_path(self, original_path: str) -> str:
        """Get themed icon path."""
        return self._theme_service.get_icon_path(original_path)

    def get_stylesheet(self) -> str:
        """
        Get compiled stylesheet from modular QSS files.

        Falls back to base.qss if styles/ folder doesn't exist.
        """
        if self._styles_path.exists():
            return self._load_modular_stylesheet()
        return self._theme_service.get_stylesheet()

    def _load_modular_stylesheet(self) -> str:
        """Load and concatenate modular QSS files."""
        combined_qss = []

        for module_name in self.QSS_MODULES:
            module_path = self._styles_path / module_name
            if module_path.exists():
                try:
                    content = module_path.read_text(encoding="utf-8")
                    combined_qss.append(f"/* === {module_name} === */\n{content}")
                except Exception as e:
                    logger.warning(f"[ThemeManager] Failed to load {module_name}: {e}")

        # Compile with variables
        template = "\n\n".join(combined_qss)
        return self._compile_template(template)

    def _compile_template(self, template: str) -> str:
        """Replace ${variable} placeholders with actual values."""
        replacements = self._get_merged_variables()

        for key, value in replacements.items():
            template = template.replace(f"${{{key}}}", str(value))

        return template

    def _get_merged_variables(self) -> dict:
        """Get merged common + theme variables."""
        import json

        json_path = self._base_path / "variables.json"
        try:
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                common = {k: v for k, v in data.get("common", {}).items() if not k.startswith("__")}
                theme_vars = {k: v for k, v in data.get(self.current_theme, {}).items() if not k.startswith("__")}
                return {**common, **theme_vars}
        except Exception as e:
            logger.error(f"[ThemeManager] Failed to load variables: {e}")

        return {}


_theme_manager_instance: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global ThemeManager instance."""
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = ThemeManager()
    return _theme_manager_instance


__all__ = ["ThemeManager", "get_theme_manager"]
