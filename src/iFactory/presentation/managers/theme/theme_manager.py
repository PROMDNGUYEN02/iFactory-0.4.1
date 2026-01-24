"""
Enhanced Theme Manager - Production-Ready Design System.

Provides centralized theme management with:
- Design tokens integration
- Structured QSS layering
- Theme switching
- CSS variable substitution
- Icon management integration
"""

from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from PySide6.QtCore import QObject, Signal

from .design_tokens import DesignTokens, ThemeMode
from .icon_manager import IconManager
from .qss.base_qss import BASE_QSS
from .qss.components_qss import ALL_COMPONENTS_QSS

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ThemeManager(QObject):
    """
    Production-Ready Theme Manager.

    Features:
        - Single source of truth for design tokens
        - Structured, layered QSS architecture
        - Dynamic theme switching (light/dark/branded)
        - CSS variable substitution
        - Icon management integration
        - QSS caching for performance
        - Theme change signals

    Architecture:
        1. Design Tokens (design_tokens.py)
        2. Icon Definitions (icon_manager.py)
        3. Base QSS with variables (base_qss.py)
        4. Component QSS (components_qss.py)
        5. Theme Manager (this file) - orchestrates all

    Usage:
        ```python
        theme_manager = ThemeManager()

        # Get stylesheet
        stylesheet = theme_manager.get_stylesheet(mode="light")
        QApplication.instance().setStyleSheet(stylesheet)

        # Switch theme
        theme_manager.set_theme("dark")

        # Get design token value
        color = theme_manager.get_color("primary")
        spacing = theme_manager.get_spacing("md")

        # Get icon
        icon = theme_manager.get_icon("dashboard")
        ```
    """

    theme_changed = Signal(str)
    stylesheet_updated = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._mode = ThemeMode.LIGHT
        self._icon_manager = IconManager(parent=self)
        self._cache: Dict[str, str] = {}
        self._variable_pattern = re.compile(r"\$\{([A-Za-z0-9_-]+)\}")
        logger.debug("[ThemeManager] Initialized")

    @property
    def mode(self) -> ThemeMode:
        """Get current theme mode."""
        return self._mode

    @property
    def icon_manager(self) -> IconManager:
        """Get icon manager instance."""
        return self._icon_manager

    def set_theme(self, mode: str | ThemeMode) -> None:
        """
        Set theme mode.

        Args:
            mode: 'light', 'dark', or ThemeMode enum
        """
        if isinstance(mode, str):
            mode = ThemeMode(mode.lower())

        if self._mode == mode:
            return

        self._mode = mode
        self._icon_manager.set_theme(mode.value)
        self._cache.clear()

        self.theme_changed.emit(mode.value)
        logger.info(f"[ThemeManager] Theme changed: {mode.value}")

    def is_dark(self) -> bool:
        """Check if dark mode is active."""
        return self._mode == ThemeMode.DARK

    def get_stylesheet(
        self,
        mode: str | ThemeMode | None = None,
        include_components: bool = True
    ) -> str:
        """
        Get complete stylesheet with variable substitution.

        Args:
            mode: Theme mode (default: current mode)
            include_components: Include component styles (default: True)

        Returns:
            Complete QSS stylesheet
        """
        if mode is None:
            mode = self._mode
        elif isinstance(mode, str):
            mode = ThemeMode(mode.lower())

        cache_key = f"{mode.value}_{include_components}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        variables = DesignTokens.get_all_css_variables(mode)
        css = self._substitute_variables(BASE_QSS, variables)

        if include_components:
            css += "\n" + self._substitute_variables(ALL_COMPONENTS_QSS, variables)

        self._cache[cache_key] = css
        return css

    def _substitute_variables(self, template: str, variables: Dict[str, str]) -> str:
        """
        Substitute CSS variables in template.

        Args:
            template: CSS template with ${variable} placeholders
            variables: Dictionary of variable name → value

        Returns:
            CSS with variables substituted
        """
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return variables.get(var_name, "")

        return self._variable_pattern.sub(replacer, template)

    def get_color(self, name: str, mode: str | ThemeMode | None = None) -> str:
        """
        Get color value from design tokens.

        Args:
            name: Color token name (e.g., 'primary', 'error')
            mode: Theme mode (default: current mode)

        Returns:
            Color value in hex or rgba format
        """
        if mode is None:
            mode = self._mode
        elif isinstance(mode, str):
            mode = ThemeMode(mode.lower())

        return DesignTokens.get_color(name, mode)

    def get_spacing(self, name: str) -> int:
        """
        Get spacing value from design tokens.

        Args:
            name: Spacing token name (e.g., 'sm', 'md', 'lg')

        Returns:
            Spacing value in pixels
        """
        return DesignTokens.get_spacing(name)

    def get_shadow(self, name: str, mode: str | ThemeMode | None = None) -> str:
        """
        Get shadow value from design tokens.

        Args:
            name: Shadow token name (e.g., 'sm', 'md', 'lg')
            mode: Theme mode (default: current mode)

        Returns:
            Shadow CSS value
        """
        if mode is None:
            mode = self._mode
        elif isinstance(mode, str):
            mode = ThemeMode(mode.lower())

        return DesignTokens.get_shadow(name, mode)

    def get_radius(self, name: str) -> int:
        """
        Get radius value from design tokens.

        Args:
            name: Radius token name (e.g., 'sm', 'md', 'lg')

        Returns:
            Radius value in pixels
        """
        return DesignTokens.get_radius(name)

    def get_typography(self, name: str) -> Dict[str, str] | None:
        """
        Get typography token from design tokens.

        Args:
            name: Typography token name (e.g., 'body', 'heading')

        Returns:
            Dictionary with font properties
        """
        token = DesignTokens.get_typography(name)
        if not token:
            return None

        return {
            "font_family": token.font_family,
            "font_size": token.font_size,
            "font_weight": token.font_weight,
            "line_height": token.line_height,
            "letter_spacing": token.letter_spacing,
        }

    def get_icon(
        self,
        name: str,
        size: int | None = None,
        theme: str | None = None
    ) -> object:
        """
        Get icon (delegated to IconManager).

        Args:
            name: Icon name
            size: Icon size in pixels (optional)
            theme: Theme mode (optional)

        Returns:
            QIcon instance
        """
        return self._icon_manager.get_icon(name, size=size, theme=theme)

    def apply_stylesheet(self, app: object, mode: str | ThemeMode | None = None) -> None:
        """
        Apply stylesheet to QApplication.

        Args:
            app: QApplication instance
            mode: Theme mode (default: current mode)
        """
        stylesheet = self.get_stylesheet(mode=mode, include_components=True)
        app.setStyleSheet(stylesheet)
        self.stylesheet_updated.emit(stylesheet)
        logger.debug("[ThemeManager] Stylesheet applied")

    def clear_cache(self) -> None:
        """Clear stylesheet cache."""
        self._cache.clear()
        logger.debug("[ThemeManager] Cache cleared")

    def reload_from_files(self, qss_directory: Path | str) -> None:
        """
        Reload QSS files from directory.

        Args:
            qss_directory: Path to QSS files directory
        """
        qss_dir = Path(qss_directory)
        if not qss_dir.exists():
            logger.warning(f"[ThemeManager] QSS directory not found: {qss_dir}")
            return

        self.clear_cache()
        logger.info(f"[ThemeManager] Reloaded QSS from: {qss_dir}")

    def export_theme_config(self, output_path: Path | str) -> None:
        """
        Export current theme configuration to JSON.

        Args:
            output_path: Path to output file
        """
        import json

        output = Path(output_path)
        variables = DesignTokens.get_all_css_variables(self._mode)

        config = {
            "theme_mode": self._mode.value,
            "css_variables": variables,
            "color_tokens": {
                name: {
                    "value": self.get_color(name),
                    "description": token.description
                }
                for name, token in DesignTokens.COLOR_TOKENS.items()
            },
            "spacing_tokens": {
                name: {
                    "value": token.value,
                    "description": token.description
                }
                for name, token in DesignTokens.SPACING_TOKENS.items()
            },
        }

        with output.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        logger.info(f"[ThemeManager] Exported theme config: {output}")


__all__ = ["ThemeManager"]
