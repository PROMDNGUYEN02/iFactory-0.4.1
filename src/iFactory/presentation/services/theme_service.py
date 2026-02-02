# File: presentation/services/theme_service.py
"""
Theme Service - Single Source of Truth for theming.

Responsibilities:
- Load and cache theme variables
- Compile and cache stylesheets
- Provide semantic color tokens
- Emit theme change signals
- Provide icon path resolution (delegates to IconProvider)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap

if TYPE_CHECKING:
    from ..resources.icons import Icons, DeviceIcons

logger = logging.getLogger(__name__)


class ThemeTokens:
    """
    Semantic color tokens for type-safe theme access.

    Usage:
        tokens = theme_service.tokens
        color = tokens.app_bg  # Returns hex string
        qcolor = tokens.get_qcolor("app.bg")  # Returns QColor
    """

    def __init__(self, variables: Dict[str, str]):
        self._vars = variables

    # App colors
    @property
    def app_bg(self) -> str:
        return self._vars.get("app.bg", "#FFFFFF")

    @property
    def app_fg(self) -> str:
        return self._vars.get("app.fg", "#000000")

    @property
    def slide_bg(self) -> str:
        return self._vars.get("slide.bg", "#FFFFFF")

    @property
    def stack_bg(self) -> str:
        return self._vars.get("stack.bg", "#F1F5F9")

    @property
    def frame_bg(self) -> str:
        return self._vars.get("frame.bg", "#FFFFFF")

    @property
    def border(self) -> str:
        return self._vars.get("border", "#E2E8F0")

    @property
    def hover(self) -> str:
        return self._vars.get("hover", "#F1F5F9")

    @property
    def selected(self) -> str:
        return self._vars.get("selected", "#EFF6FF")

    @property
    def selected_text(self) -> str:
        return self._vars.get("selected.text", "#2563EB")

    @property
    def selected_border(self) -> str:
        return self._vars.get("selected.border", "#BFDBFE")

    @property
    def hint(self) -> str:
        return self._vars.get("hint", "#94A3B8")

    # Semantic colors
    @property
    def accent(self) -> str:
        return self._vars.get("accent", "#3B82F6")

    @property
    def success(self) -> str:
        return self._vars.get("success", "#10B981")

    @property
    def warning(self) -> str:
        return self._vars.get("warning", "#F59E0B")

    @property
    def error(self) -> str:
        return self._vars.get("error", "#EF4444")

    # Status colors
    @property
    def status_unknown(self) -> str:
        return self._vars.get("status.unknown", "#94A3B8")

    @property
    def status_running(self) -> str:
        return self._vars.get("status.running", "#10B981")

    @property
    def status_shutdown(self) -> str:
        return self._vars.get("status.shutdown", "#64748B")

    @property
    def status_stopped(self) -> str:
        return self._vars.get("status.stopped", "#F59E0B")

    @property
    def status_maintenance(self) -> str:
        return self._vars.get("status.maintenance", "#06B6D4")

    @property
    def status_alarm(self) -> str:
        return self._vars.get("status.alarm", "#EF4444")

    # Chart colors
    @property
    def chart_bg(self) -> str:
        return self._vars.get("chart.bg", "#FFFFFF")

    @property
    def chart_grid(self) -> str:
        return self._vars.get("chart.grid", "#E2E8F0")

    @property
    def chart_text(self) -> str:
        return self._vars.get("chart.text", "#475569")

    @property
    def chart_now(self) -> str:
        return self._vars.get("chart.now", "#EF4444")

    # Common tokens
    @property
    def font_family(self) -> str:
        return self._vars.get("font.family", "Segoe UI")

    @property
    def radius(self) -> str:
        return self._vars.get("radius", "8px")

    @property
    def radius_sm(self) -> str:
        return self._vars.get("radius.sm", "6px")

    @property
    def radius_lg(self) -> str:
        return self._vars.get("radius.lg", "12px")

    def get(self, key: str, default: str = "#FF00FF") -> str:
        """Get any token by key."""
        return self._vars.get(key, default)

    def get_qcolor(self, key: str) -> QColor:
        """Get color as QColor."""
        return QColor(self.get(key))

    def get_rgba(self, key: str, alpha: float = 1.0) -> str:
        """Get color as rgba() string."""
        color = QColor(self.get(key))
        r, g, b = color.red(), color.green(), color.blue()
        return f"rgba({r}, {g}, {b}, {alpha})"


class ThemeService(QObject):
    """
    Central theme management service.

    Features:
    - Single source of truth for theme state
    - Cached stylesheet compilation
    - Semantic color tokens
    - Icon resolution with caching
    - Reactive theme change signals
    """

    themeChanged = Signal(str)  # Emits theme name ("light" or "dark")

    def __init__(self, base_path: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._base_path = base_path or Path(__file__).parent.parent / "resources" / "themes"
        self._current_theme: str = "light"
        self._variables: Dict[str, Any] = {}
        self._stylesheet_cache: Dict[str, str] = {}
        self._tokens_cache: Dict[str, ThemeTokens] = {}

        # Lazy-loaded icon provider
        self._icon_provider = None

        self._load_variables()

    def _load_variables(self) -> None:
        """Load theme variables from JSON (once)."""
        json_path = self._base_path / "variables.json"
        try:
            if json_path.exists():
                text = json_path.read_text(encoding="utf-8")
                self._variables = json.loads(text)
                logger.info(f"[ThemeService] Loaded variables from {json_path}")
            else:
                logger.warning(f"[ThemeService] Variables not found: {json_path}")
                self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}
        except Exception as e:
            logger.error(f"[ThemeService] Failed to load variables: {e}")
            self._variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}

    def _get_icon_provider(self):
        """Lazy-load icon provider to avoid circular imports."""
        if self._icon_provider is None:
            from ..resources.icons import get_icon_provider

            self._icon_provider = get_icon_provider(self)
        return self._icon_provider

    # =========================================================================
    # Theme State
    # =========================================================================

    @property
    def current_theme(self) -> str:
        """Get current theme name."""
        return self._current_theme

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark."""
        return self._current_theme == "dark"

    def set_theme(self, theme: str) -> None:
        """Set the current theme. Emits themeChanged if changed."""
        if theme not in ("light", "dark"):
            logger.warning(f"[ThemeService] Invalid theme: {theme}")
            return

        if theme != self._current_theme:
            self._current_theme = theme
            logger.info(f"[ThemeService] Theme changed to: {theme}")
            self.themeChanged.emit(theme)

    def toggle_theme(self) -> str:
        """Toggle between light and dark theme. Returns new theme."""
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.set_theme(new_theme)
        return new_theme

    # =========================================================================
    # Color Access
    # =========================================================================

    @property
    def tokens(self) -> ThemeTokens:
        """Get semantic color tokens for current theme. Cached per theme."""
        if self._current_theme not in self._tokens_cache:
            merged = self._get_merged_variables()
            self._tokens_cache[self._current_theme] = ThemeTokens(merged)
        return self._tokens_cache[self._current_theme]

    def get_color(self, key: str, default: str = "#FF00FF") -> str:
        """Get a color value by key."""
        return self.tokens.get(key, default)

    def get_qcolor(self, key: str) -> QColor:
        """Get a color as QColor."""
        return self.tokens.get_qcolor(key)

    def _get_merged_variables(self) -> Dict[str, str]:
        """Merge common and theme-specific variables."""
        common = self._variables.get("common", {})
        theme_vars = self._variables.get(self._current_theme, {})
        return {**common, **theme_vars}

    # =========================================================================
    # Stylesheet
    # =========================================================================

    def get_stylesheet(self) -> str:
        """Get compiled stylesheet for current theme. Cached."""
        cache_key = self._current_theme

        if cache_key in self._stylesheet_cache:
            return self._stylesheet_cache[cache_key]

        stylesheet = self._compile_stylesheet()
        self._stylesheet_cache[cache_key] = stylesheet
        return stylesheet

    def _compile_stylesheet(self) -> str:
        """Compile QSS template with current theme variables."""
        qss_path = self._base_path / "base.qss"

        try:
            if not qss_path.exists():
                logger.warning(f"[ThemeService] QSS not found: {qss_path}")
                return ""

            template = qss_path.read_text(encoding="utf-8")
            replacements = self._get_merged_variables()

            for key, value in replacements.items():
                template = template.replace(f"${{{key}}}", str(value))

            return template

        except Exception as e:
            logger.error(f"[ThemeService] Failed to compile stylesheet: {e}")
            return ""

    def invalidate_cache(self) -> None:
        """Clear all caches. Call after modifying variables.json."""
        self._stylesheet_cache.clear()
        self._tokens_cache.clear()
        self._load_variables()

    # =========================================================================
    # Icon Resolution (Delegates to IconProvider)
    # =========================================================================

    def get_icon_path(self, icon_or_path: Union["Icons", "DeviceIcons", str]) -> str:
        """
        Resolve icon path for current theme.

        Supports both enum-based icons (preferred) and legacy string paths.

        Args:
            icon_or_path: Icons enum, DeviceIcons enum, or legacy string path

        Returns:
            Theme-appropriate resource path
        """
        return self._get_icon_provider().resolve_path(icon_or_path)

    def get_icon(self, icon_or_path: Union["Icons", "DeviceIcons", str]) -> QIcon:
        """
        Get cached QIcon for the given icon.

        Args:
            icon_or_path: Icons enum, DeviceIcons enum, or legacy string path

        Returns:
            Cached QIcon instance
        """
        return self._get_icon_provider().get_icon(icon_or_path)

    def get_pixmap(self, icon_or_path: Union["Icons", "DeviceIcons", str], size: Optional[QSize] = None) -> QPixmap:
        """
        Get cached QPixmap for the given icon.

        Args:
            icon_or_path: Icons enum, DeviceIcons enum, or legacy string path
            size: Desired size

        Returns:
            Cached QPixmap instance
        """
        return self._get_icon_provider().get_pixmap(icon_or_path, size)

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get icon for a device by equipment code."""
        return self._get_icon_provider().get_device_icon(equipment_code)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get pixmap for a device by equipment code."""
        return self._get_icon_provider().get_device_pixmap(equipment_code, size)

    def preload_icons(self, icons: list) -> None:
        """Preload icons for faster access."""
        self._get_icon_provider().preload(icons)

    # =========================================================================
    # Component Styles (Pre-computed helpers)
    # =========================================================================

    def get_panel_style(self, panel_type: str = "left") -> str:
        """Get pre-computed style for panel frames."""
        tokens = self.tokens
        border_side = "right" if panel_type == "left" else "left"

        return f"""
            background-color: {tokens.get_rgba("slide.bg", 0.98)};
            border: none;
            border-{border_side}: 1px solid {tokens.get_rgba("border", 0.5)};
        """

    def get_card_style(self) -> str:
        """Get pre-computed style for card frames."""
        tokens = self.tokens

        return f"""
            background-color: {tokens.get_rgba("frame.bg", 0.8)};
            border: 1px solid {tokens.get_rgba("border", 0.6)};
            border-radius: {tokens.radius};
        """

    def get_progress_bar_style(self, color: Optional[str] = None) -> str:
        """Get pre-computed progress bar style."""
        tokens = self.tokens
        bar_color = color or tokens.accent

        return f"""
            QProgressBar {{
                background-color: {tokens.hover};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 4px;
            }}
        """


# =========================================================================
# Factory functions for dependency injection
# =========================================================================

_theme_service_instance: Optional[ThemeService] = None


def get_theme_service() -> ThemeService:
    """Get the global ThemeService instance."""
    global _theme_service_instance
    if _theme_service_instance is None:
        _theme_service_instance = ThemeService()
    return _theme_service_instance


def create_theme_service(base_path: Optional[Path] = None) -> ThemeService:
    """Create a new ThemeService instance (for testing)."""
    return ThemeService(base_path=base_path)


__all__ = [
    "ThemeService",
    "ThemeTokens",
    "get_theme_service",
    "create_theme_service",
]
