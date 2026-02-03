# File: presentation/services/theme_service.py
"""
Theme Service - Single Source of Truth for theming.

OPTIMIZED VERSION:
1. Load variables.json ONCE on init
2. Cache merged variables per theme
3. Cache QSS template (raw files concatenated)
4. Use regex for faster template compilation
5. Lazy icon provider loading
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from iFactory.infrastructure.configuration.paths import PATHS

if TYPE_CHECKING:
    from ..resources.icons import Icons, DeviceIcons

logger = logging.getLogger(__name__)


class ThemeTokens:
    """
    Semantic design tokens for type-safe theme access.

    OPTIMIZED: Uses __slots__ for memory efficiency.
    """

    __slots__ = ("_vars",)

    def __init__(self, variables: Dict[str, str]):
        self._vars = variables

    # =========================================================================
    # LEGACY ALIASES (Backward Compatibility)
    # =========================================================================
    @property
    def app_bg(self) -> str:
        return self.surface_app

    @property
    def app_fg(self) -> str:
        return self.text_primary

    @property
    def slide_bg(self) -> str:
        return self.surface_panel

    @property
    def stack_bg(self) -> str:
        return self._vars.get("stack.bg", self.surface_app)

    @property
    def frame_bg(self) -> str:
        return self.surface_card

    @property
    def border(self) -> str:
        return self.border_default

    @property
    def hover(self) -> str:
        return self.interactive_hover

    @property
    def selected(self) -> str:
        return self.interactive_selected_bg

    @property
    def selected_text(self) -> str:
        return self.interactive_selected_text

    @property
    def selected_border(self) -> str:
        return self._vars.get("selected.border", self._vars.get("interactive.selected.border", "#BFDBFE"))

    @property
    def hint(self) -> str:
        return self.text_muted

    @property
    def accent(self) -> str:
        return self.primary

    @property
    def icon_hover(self) -> str:
        return self._vars.get("icon.hover", self.interactive_hover)

    @property
    def icon_border(self) -> str:
        return self._vars.get("icon.border", "transparent")

    # =========================================================================
    # SURFACES
    # =========================================================================
    @property
    def surface_app(self) -> str:
        return self._vars.get("surface.app", self._vars.get("app.bg", "#FFFFFF"))

    @property
    def surface_panel(self) -> str:
        return self._vars.get("surface.panel", self._vars.get("slide.bg", "#FFFFFF"))

    @property
    def surface_card(self) -> str:
        return self._vars.get("surface.card", self._vars.get("frame.bg", "#FFFFFF"))

    @property
    def surface_elevated(self) -> str:
        return self._vars.get("surface.elevated", "#FFFFFF")

    @property
    def surface_overlay(self) -> str:
        return self._vars.get("surface.overlay", "rgba(0, 0, 0, 0.5)")

    # =========================================================================
    # TEXT
    # =========================================================================
    @property
    def text_primary(self) -> str:
        return self._vars.get("text.primary", self._vars.get("app.fg", "#000000"))

    @property
    def text_secondary(self) -> str:
        return self._vars.get("text.secondary", "#475569")

    @property
    def text_tertiary(self) -> str:
        return self._vars.get("text.tertiary", "#64748B")

    @property
    def text_muted(self) -> str:
        return self._vars.get("text.muted", self._vars.get("hint", "#94A3B8"))

    @property
    def text_inverse(self) -> str:
        return self._vars.get("text.inverse", "#FFFFFF")

    @property
    def text_link(self) -> str:
        return self._vars.get("text.link", "#2563EB")

    @property
    def text_link_hover(self) -> str:
        return self._vars.get("text.link.hover", "#1D4ED8")

    # =========================================================================
    # BORDERS
    # =========================================================================
    @property
    def border_default(self) -> str:
        return self._vars.get("border.default", self._vars.get("border", "#E2E8F0"))

    @property
    def border_subtle(self) -> str:
        return self._vars.get("border.subtle", "#F1F5F9")

    @property
    def border_strong(self) -> str:
        return self._vars.get("border.strong", "#CBD5E1")

    @property
    def border_focus(self) -> str:
        return self._vars.get("border.focus", "#3B82F6")

    # =========================================================================
    # INTERACTIVE STATES
    # =========================================================================
    @property
    def interactive_hover(self) -> str:
        return self._vars.get("interactive.hover", self._vars.get("hover", "#F1F5F9"))

    @property
    def interactive_active(self) -> str:
        return self._vars.get("interactive.active", "#E2E8F0")

    @property
    def interactive_selected_bg(self) -> str:
        return self._vars.get("interactive.selected.bg", self._vars.get("selected", "#EFF6FF"))

    @property
    def interactive_selected_text(self) -> str:
        return self._vars.get("interactive.selected.text", self._vars.get("selected.text", "#2563EB"))

    @property
    def interactive_selected_border(self) -> str:
        return self._vars.get("interactive.selected.border", self._vars.get("selected.border", "#BFDBFE"))

    @property
    def interactive_disabled_bg(self) -> str:
        return self._vars.get("interactive.disabled.bg", "#F1F5F9")

    @property
    def interactive_disabled_text(self) -> str:
        return self._vars.get("interactive.disabled.text", "#94A3B8")

    # =========================================================================
    # SEMANTIC COLORS
    # =========================================================================
    @property
    def primary(self) -> str:
        return self._vars.get("semantic.primary", self._vars.get("accent", "#3B82F6"))

    @property
    def primary_hover(self) -> str:
        return self._vars.get("semantic.primary.hover", "#2563EB")

    @property
    def primary_active(self) -> str:
        return self._vars.get("semantic.primary.active", "#1D4ED8")

    @property
    def primary_subtle(self) -> str:
        return self._vars.get("semantic.primary.subtle", "#EFF6FF")

    @property
    def success(self) -> str:
        return self._vars.get("semantic.success", self._vars.get("success", "#10B981"))

    @property
    def success_hover(self) -> str:
        return self._vars.get("semantic.success.hover", "#059669")

    @property
    def success_subtle(self) -> str:
        return self._vars.get("semantic.success.subtle", "#ECFDF5")

    @property
    def warning(self) -> str:
        return self._vars.get("semantic.warning", self._vars.get("warning", "#F59E0B"))

    @property
    def warning_hover(self) -> str:
        return self._vars.get("semantic.warning.hover", "#D97706")

    @property
    def warning_subtle(self) -> str:
        return self._vars.get("semantic.warning.subtle", "#FFFBEB")

    @property
    def error(self) -> str:
        return self._vars.get("semantic.error", self._vars.get("error", "#EF4444"))

    @property
    def error_hover(self) -> str:
        return self._vars.get("semantic.error.hover", "#DC2626")

    @property
    def error_subtle(self) -> str:
        return self._vars.get("semantic.error.subtle", "#FEF2F2")

    @property
    def info(self) -> str:
        return self._vars.get("semantic.info", "#06B6D4")

    @property
    def info_hover(self) -> str:
        return self._vars.get("semantic.info.hover", "#0891B2")

    @property
    def info_subtle(self) -> str:
        return self._vars.get("semantic.info.subtle", "#ECFEFF")

    # =========================================================================
    # MACHINE STATUS
    # =========================================================================
    @property
    def status_unknown(self) -> str:
        return self._vars.get("status.unknown", "#94A3B8")

    @property
    def status_unknown_bg(self) -> str:
        return self._vars.get("status.unknown.bg", "#F1F5F9")

    @property
    def status_running(self) -> str:
        return self._vars.get("status.running", "#10B981")

    @property
    def status_running_bg(self) -> str:
        return self._vars.get("status.running.bg", "#ECFDF5")

    @property
    def status_shutdown(self) -> str:
        return self._vars.get("status.shutdown", "#64748B")

    @property
    def status_shutdown_bg(self) -> str:
        return self._vars.get("status.shutdown.bg", "#F1F5F9")

    @property
    def status_stopped(self) -> str:
        return self._vars.get("status.stopped", "#F59E0B")

    @property
    def status_stopped_bg(self) -> str:
        return self._vars.get("status.stopped.bg", "#FFFBEB")

    @property
    def status_maintenance(self) -> str:
        return self._vars.get("status.maintenance", "#06B6D4")

    @property
    def status_maintenance_bg(self) -> str:
        return self._vars.get("status.maintenance.bg", "#ECFEFF")

    @property
    def status_alarm(self) -> str:
        return self._vars.get("status.alarm", "#EF4444")

    @property
    def status_alarm_bg(self) -> str:
        return self._vars.get("status.alarm.bg", "#FEF2F2")

    # =========================================================================
    # CHART
    # =========================================================================
    @property
    def chart_bg(self) -> str:
        return self._vars.get("chart.bg", "#FFFFFF")

    @property
    def chart_grid(self) -> str:
        return self._vars.get("chart.grid", "#E2E8F0")

    @property
    def chart_axis(self) -> str:
        return self._vars.get("chart.axis", "#94A3B8")

    @property
    def chart_text(self) -> str:
        return self._vars.get("chart.text", "#475569")

    @property
    def chart_now(self) -> str:
        return self._vars.get("chart.now", "#EF4444")

    # =========================================================================
    # TOOLTIP
    # =========================================================================
    @property
    def tooltip_bg(self) -> str:
        return self._vars.get("tooltip.bg", "#1E293B")

    @property
    def tooltip_text(self) -> str:
        return self._vars.get("tooltip.text", "#F8FAFC")

    @property
    def tooltip_border(self) -> str:
        return self._vars.get("tooltip.border", "#334155")

    # =========================================================================
    # SCROLLBAR
    # =========================================================================
    @property
    def scrollbar_track(self) -> str:
        return self._vars.get("scrollbar.track", "transparent")

    @property
    def scrollbar_thumb(self) -> str:
        return self._vars.get("scrollbar.thumb", "#CBD5E1")

    @property
    def scrollbar_thumb_hover(self) -> str:
        return self._vars.get("scrollbar.thumb.hover", "#94A3B8")

    # =========================================================================
    # TYPOGRAPHY
    # =========================================================================
    @property
    def font_family(self) -> str:
        return self._vars.get("font.family.primary", self._vars.get("font.family", "Segoe UI"))

    @property
    def font_family_mono(self) -> str:
        return self._vars.get("font.family.mono", "Consolas")

    @property
    def font_size_xs(self) -> str:
        return self._vars.get("font.size.xs", "10px")

    @property
    def font_size_sm(self) -> str:
        return self._vars.get("font.size.sm", "11px")

    @property
    def font_size_base(self) -> str:
        return self._vars.get("font.size.base", "13px")

    @property
    def font_size_md(self) -> str:
        return self._vars.get("font.size.md", "14px")

    @property
    def font_size_lg(self) -> str:
        return self._vars.get("font.size.lg", "16px")

    @property
    def font_size_xl(self) -> str:
        return self._vars.get("font.size.xl", "18px")

    @property
    def font_size_2xl(self) -> str:
        return self._vars.get("font.size.2xl", "24px")

    @property
    def font_weight_normal(self) -> str:
        return self._vars.get("font.weight.normal", "400")

    @property
    def font_weight_medium(self) -> str:
        return self._vars.get("font.weight.medium", "500")

    @property
    def font_weight_semibold(self) -> str:
        return self._vars.get("font.weight.semibold", "600")

    @property
    def font_weight_bold(self) -> str:
        return self._vars.get("font.weight.bold", "700")

    # =========================================================================
    # SPACING (8pt grid)
    # =========================================================================
    @property
    def space_0(self) -> str:
        return self._vars.get("space.0", "0px")

    @property
    def space_1(self) -> str:
        return self._vars.get("space.1", "4px")

    @property
    def space_2(self) -> str:
        return self._vars.get("space.2", "8px")

    @property
    def space_3(self) -> str:
        return self._vars.get("space.3", "12px")

    @property
    def space_4(self) -> str:
        return self._vars.get("space.4", "16px")

    @property
    def space_5(self) -> str:
        return self._vars.get("space.5", "20px")

    @property
    def space_6(self) -> str:
        return self._vars.get("space.6", "24px")

    @property
    def space_8(self) -> str:
        return self._vars.get("space.8", "32px")

    @property
    def space_10(self) -> str:
        return self._vars.get("space.10", "40px")

    @property
    def space_12(self) -> str:
        return self._vars.get("space.12", "48px")

    # =========================================================================
    # RADIUS
    # =========================================================================
    @property
    def radius_none(self) -> str:
        return self._vars.get("radius.none", "0px")

    @property
    def radius_sm(self) -> str:
        return self._vars.get("radius.sm", "4px")

    @property
    def radius_base(self) -> str:
        return self._vars.get("radius.base", "6px")

    @property
    def radius(self) -> str:
        return self.radius_md

    @property
    def radius_md(self) -> str:
        return self._vars.get("radius.md", self._vars.get("radius", "8px"))

    @property
    def radius_lg(self) -> str:
        return self._vars.get("radius.lg", "12px")

    @property
    def radius_xl(self) -> str:
        return self._vars.get("radius.xl", "16px")

    @property
    def radius_full(self) -> str:
        return self._vars.get("radius.full", "9999px")

    # =========================================================================
    # SHADOWS
    # =========================================================================
    @property
    def shadow_sm(self) -> str:
        return self._vars.get("shadow.sm", "0 1px 2px 0 rgba(0, 0, 0, 0.05)")

    @property
    def shadow_base(self) -> str:
        return self._vars.get("shadow.base", "0 1px 3px 0 rgba(0, 0, 0, 0.1)")

    @property
    def shadow_md(self) -> str:
        return self._vars.get("shadow.md", "0 4px 6px -1px rgba(0, 0, 0, 0.1)")

    @property
    def shadow_lg(self) -> str:
        return self._vars.get("shadow.lg", "0 10px 15px -3px rgba(0, 0, 0, 0.1)")

    @property
    def shadow_xl(self) -> str:
        return self._vars.get("shadow.xl", "0 20px 25px -5px rgba(0, 0, 0, 0.1)")

    # =========================================================================
    # LAYOUT
    # =========================================================================
    @property
    def layout_sidebar_collapsed(self) -> str:
        return self._vars.get("layout.sidebar.collapsed", "60px")

    @property
    def layout_sidebar_expanded(self) -> str:
        return self._vars.get("layout.sidebar.expanded", "220px")

    @property
    def layout_header_height(self) -> str:
        return self._vars.get("layout.header.height", "48px")

    @property
    def layout_statusbar_height(self) -> str:
        return self._vars.get("layout.statusbar.height", "28px")

    @property
    def layout_panel_width(self) -> str:
        return self._vars.get("layout.panel.width", "320px")

    @property
    def layout_gantt_row_height(self) -> str:
        return self._vars.get("layout.gantt.row.height", "32px")

    @property
    def layout_gantt_row_compact(self) -> str:
        return self._vars.get("layout.gantt.row.compact", "20px")

    # =========================================================================
    # COMPONENT SIZING
    # =========================================================================
    @property
    def size_icon_sm(self) -> str:
        return self._vars.get("size.icon.sm", "16px")

    @property
    def size_icon_base(self) -> str:
        return self._vars.get("size.icon.base", "20px")

    @property
    def size_icon_md(self) -> str:
        return self._vars.get("size.icon.md", "24px")

    @property
    def size_icon_lg(self) -> str:
        return self._vars.get("size.icon.lg", "32px")

    @property
    def size_button_height_sm(self) -> str:
        return self._vars.get("size.button.height.sm", "28px")

    @property
    def size_button_height_base(self) -> str:
        return self._vars.get("size.button.height.base", "36px")

    @property
    def size_button_height_lg(self) -> str:
        return self._vars.get("size.button.height.lg", "44px")

    @property
    def size_input_height(self) -> str:
        return self._vars.get("size.input.height", "36px")

    # =========================================================================
    # ANIMATION
    # =========================================================================
    @property
    def transition_fast(self) -> str:
        return self._vars.get("transition.fast", "150ms")

    @property
    def transition_base(self) -> str:
        return self._vars.get("transition.base", "200ms")

    @property
    def transition_slow(self) -> str:
        return self._vars.get("transition.slow", "300ms")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
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

    def get_int(self, key: str, default: int = 0) -> int:
        """Get numeric value (strips 'px' suffix)."""
        value = self.get(key, str(default))
        return int(value.replace("px", "").replace("ms", "").strip())


class ThemeService(QObject):
    """
    Central theme management service - OPTIMIZED.

    Key optimizations:
    1. Load variables.json ONCE on init
    2. Cache merged variables per theme (both light/dark precomputed)
    3. Load QSS template ONCE on init
    4. Use regex for faster template compilation
    5. Lazy icon provider loading
    6. Style method caching
    """

    themeChanged = Signal(str)

    # QSS modules to load (in order)
    QSS_MODULES = [
        "_global.qss",
        "_scrollbar.qss",
        "_buttons.qss",
        "_inputs.qss",
        "_panels.qss",
        "_cards.qss",
        "_status.qss",
        "_tooltips.qss",
    ]

    # Compiled regex for variable replacement
    _VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, base_path: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._base_path = base_path or PATHS.themes_dir
        self._styles_path = self._base_path / "styles"
        self._current_theme: str = "light"

        # === CACHED DATA (loaded once) ===
        self._raw_variables: Dict[str, Any] = {}
        self._merged_variables_cache: Dict[str, Dict[str, str]] = {}
        self._qss_template_cache: Optional[str] = None
        self._stylesheet_cache: Dict[str, str] = {}
        self._tokens_cache: Dict[str, ThemeTokens] = {}
        self._style_cache: Dict[str, str] = {}  # Pre-computed component styles
        self._icon_provider = None

        # Load everything once
        self._load_variables_once()
        self._load_qss_template_once()
        self._precompute_merged_variables()

    def _load_variables_once(self) -> None:
        """Load theme variables from JSON - ONCE on init."""
        json_path = self._base_path / "variables.json"
        try:
            if json_path.exists():
                text = json_path.read_text(encoding="utf-8")
                self._raw_variables = json.loads(text)
                logger.info(f"[ThemeService] Loaded variables.json ({len(text)} bytes)")
            else:
                logger.warning(f"[ThemeService] Variables not found: {json_path}")
                self._raw_variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}
        except Exception as e:
            logger.error(f"[ThemeService] Failed to load variables: {e}")
            self._raw_variables = {"common": {}, "light": {}, "dark": {}, "iconAlias": {}}

    def _load_qss_template_once(self) -> None:
        """Load and concatenate QSS files - ONCE on init."""
        if not self._styles_path.exists():
            # Try legacy base.qss
            legacy_path = self._base_path / "base.qss"
            if legacy_path.exists():
                try:
                    self._qss_template_cache = legacy_path.read_text(encoding="utf-8")
                    logger.info(f"[ThemeService] Loaded legacy base.qss")
                except Exception as e:
                    logger.error(f"[ThemeService] Failed to load base.qss: {e}")
            return

        combined_qss = []
        total_size = 0

        for module_name in self.QSS_MODULES:
            module_path = self._styles_path / module_name
            if module_path.exists():
                try:
                    content = module_path.read_text(encoding="utf-8")
                    combined_qss.append(f"/* === {module_name} === */\n{content}")
                    total_size += len(content)
                except Exception as e:
                    logger.warning(f"[ThemeService] Failed to load {module_name}: {e}")

        self._qss_template_cache = "\n\n".join(combined_qss)
        logger.info(f"[ThemeService] Loaded {len(self.QSS_MODULES)} QSS modules ({total_size} bytes)")

    def _precompute_merged_variables(self) -> None:
        """Pre-compute merged variables for both themes."""
        common = {k: v for k, v in self._raw_variables.get("common", {}).items() if not k.startswith("__")}

        for theme in ("light", "dark"):
            theme_vars = {k: v for k, v in self._raw_variables.get(theme, {}).items() if not k.startswith("__")}
            self._merged_variables_cache[theme] = {**common, **theme_vars}

        logger.debug(f"[ThemeService] Pre-computed variables for light/dark themes")

    def _get_icon_provider(self):
        """Lazy-load icon provider."""
        if self._icon_provider is None:
            from ..resources.icons import get_icon_provider

            self._icon_provider = get_icon_provider(self)
        return self._icon_provider

    # =========================================================================
    # Theme State
    # =========================================================================

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @property
    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def set_theme(self, theme: str) -> None:
        """Set the current theme - OPTIMIZED."""
        if theme not in ("light", "dark"):
            logger.warning(f"[ThemeService] Invalid theme: {theme}")
            return

        if theme == self._current_theme:
            return  # ⚡ Early exit - no change needed

        self._current_theme = theme

        # Clear theme-specific caches only
        self._stylesheet_cache.pop(theme, None)
        self._tokens_cache.pop(theme, None)
        self._style_cache.clear()  # Component styles depend on theme

        logger.info(f"[ThemeService] Theme changed to: {theme}")
        self.themeChanged.emit(theme)

    def toggle_theme(self) -> str:
        """Toggle between light and dark theme."""
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.set_theme(new_theme)
        return new_theme

    # =========================================================================
    # Token Access
    # =========================================================================

    @property
    def tokens(self) -> ThemeTokens:
        """Get semantic color tokens for current theme - CACHED."""
        if self._current_theme not in self._tokens_cache:
            merged = self._merged_variables_cache.get(self._current_theme, {})
            self._tokens_cache[self._current_theme] = ThemeTokens(merged)
        return self._tokens_cache[self._current_theme]

    def get_color(self, key: str, default: str = "#FF00FF") -> str:
        """Get a color value by key."""
        return self.tokens.get(key, default)

    def get_qcolor(self, key: str) -> QColor:
        """Get a color as QColor."""
        return self.tokens.get_qcolor(key)

    def _get_merged_variables(self) -> Dict[str, str]:
        """Get merged variables - uses pre-computed cache."""
        return self._merged_variables_cache.get(self._current_theme, {})

    # =========================================================================
    # Stylesheet
    # =========================================================================

    def get_stylesheet(self) -> str:
        """Get compiled stylesheet for current theme - CACHED."""
        if self._current_theme in self._stylesheet_cache:
            return self._stylesheet_cache[self._current_theme]

        if self._qss_template_cache:
            stylesheet = self._compile_template(self._qss_template_cache)
        else:
            stylesheet = ""
            logger.warning("[ThemeService] No QSS template available")

        self._stylesheet_cache[self._current_theme] = stylesheet
        return stylesheet

    def _compile_template(self, template: str) -> str:
        """Replace ${variable} placeholders - OPTIMIZED with regex."""
        replacements = self._get_merged_variables()

        def replace_var(match: re.Match) -> str:
            key = match.group(1)
            return str(replacements.get(key, match.group(0)))

        return self._VAR_PATTERN.sub(replace_var, template)

    def invalidate_cache(self) -> None:
        """Clear all caches and reload from disk."""
        self._stylesheet_cache.clear()
        self._tokens_cache.clear()
        self._merged_variables_cache.clear()
        self._style_cache.clear()
        self._qss_template_cache = None

        self._load_variables_once()
        self._load_qss_template_once()
        self._precompute_merged_variables()

        logger.info("[ThemeService] Cache invalidated and reloaded")

    # =========================================================================
    # Icon Resolution
    # =========================================================================

    def get_icon_path(self, icon_or_path: Union["Icons", "DeviceIcons", str]) -> str:
        """Resolve icon path for current theme."""
        return self._get_icon_provider().resolve_path(icon_or_path)

    def get_icon(self, icon_or_path: Union["Icons", "DeviceIcons", str]) -> QIcon:
        """Get cached QIcon."""
        return self._get_icon_provider().get_icon(icon_or_path)

    def get_pixmap(self, icon_or_path: Union["Icons", "DeviceIcons", str], size: Optional[QSize] = None) -> QPixmap:
        """Get cached QPixmap."""
        return self._get_icon_provider().get_pixmap(icon_or_path, size)

    def get_device_icon(self, equipment_code: str) -> QIcon:
        """Get icon for a device."""
        return self._get_icon_provider().get_device_icon(equipment_code)

    def get_device_pixmap(self, equipment_code: str, size: Optional[QSize] = None) -> QPixmap:
        """Get pixmap for a device."""
        return self._get_icon_provider().get_device_pixmap(equipment_code, size)

    def preload_icons(self, icons: list) -> None:
        """Preload icons for faster access."""
        self._get_icon_provider().preload(icons)

    # =========================================================================
    # Pre-computed Component Styles - CACHED
    # =========================================================================

    def _get_cached_style(self, key: str, generator: callable) -> str:
        """Get or generate cached style."""
        cache_key = f"{self._current_theme}:{key}"
        if cache_key not in self._style_cache:
            self._style_cache[cache_key] = generator()
        return self._style_cache[cache_key]

    def get_status_color(self, status: str) -> str:
        """Get color for machine status."""
        status_map = {
            "running": self.tokens.status_running,
            "stopped": self.tokens.status_stopped,
            "alarm": self.tokens.status_alarm,
            "maintenance": self.tokens.status_maintenance,
            "shutdown": self.tokens.status_shutdown,
            "unknown": self.tokens.status_unknown,
        }
        return status_map.get(status.lower(), self.tokens.status_unknown)

    def get_status_bg_color(self, status: str) -> str:
        """Get background color for machine status."""
        status_map = {
            "running": self.tokens.status_running_bg,
            "stopped": self.tokens.status_stopped_bg,
            "alarm": self.tokens.status_alarm_bg,
            "maintenance": self.tokens.status_maintenance_bg,
            "shutdown": self.tokens.status_shutdown_bg,
            "unknown": self.tokens.status_unknown_bg,
        }
        return status_map.get(status.lower(), self.tokens.status_unknown_bg)

    def get_panel_style(self, panel_type: str = "left") -> str:
        """Get pre-computed style for panel frames - CACHED."""

        def generate():
            tokens = self.tokens
            border_side = "right" if panel_type == "left" else "left"
            return f"""
                background-color: {tokens.surface_panel};
                border: none;
                border-{border_side}: 1px solid {tokens.border_default};
            """

        return self._get_cached_style(f"panel_{panel_type}", generate)

    def get_card_style(self) -> str:
        """Get pre-computed style for card frames - CACHED."""

        def generate():
            tokens = self.tokens
            return f"""
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            """

        return self._get_cached_style("card", generate)

    def get_progress_bar_style(self, color: Optional[str] = None) -> str:
        """Get pre-computed progress bar style."""
        tokens = self.tokens
        bar_color = color or tokens.primary

        # Don't cache if custom color provided
        if color:
            return f"""
                QProgressBar {{
                    background-color: {tokens.interactive_hover};
                    border: none;
                    border-radius: {tokens.radius_sm};
                    height: 6px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: {tokens.radius_sm};
                }}
            """

        def generate():
            return f"""
                QProgressBar {{
                    background-color: {tokens.interactive_hover};
                    border: none;
                    border-radius: {tokens.radius_sm};
                    height: 6px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {tokens.primary};
                    border-radius: {tokens.radius_sm};
                }}
            """

        return self._get_cached_style("progress_bar", generate)

    def get_button_style(self, variant: str = "default") -> str:
        """Get pre-computed button style - CACHED."""

        def generate():
            tokens = self.tokens

            if variant == "primary":
                return f"""
                    QPushButton {{
                        background-color: {tokens.primary};
                        border: 1px solid {tokens.primary};
                        border-radius: {tokens.radius_md};
                        padding: {tokens.space_2} {tokens.space_4};
                        color: {tokens.text_inverse};
                        font-weight: {tokens.font_weight_medium};
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.primary_hover};
                        border-color: {tokens.primary_hover};
                    }}
                    QPushButton:pressed {{
                        background-color: {tokens.primary_active};
                    }}
                    QPushButton:disabled {{
                        background-color: {tokens.interactive_disabled_bg};
                        color: {tokens.interactive_disabled_text};
                        border-color: {tokens.border_subtle};
                    }}
                """
            elif variant == "ghost":
                return f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: {tokens.radius_md};
                        padding: {tokens.space_2} {tokens.space_4};
                        color: {tokens.text_secondary};
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.interactive_hover};
                        color: {tokens.text_primary};
                    }}
                    QPushButton:pressed {{
                        background-color: {tokens.interactive_active};
                    }}
                """
            elif variant == "danger":
                return f"""
                    QPushButton {{
                        background-color: {tokens.error};
                        border: 1px solid {tokens.error};
                        border-radius: {tokens.radius_md};
                        padding: {tokens.space_2} {tokens.space_4};
                        color: {tokens.text_inverse};
                        font-weight: {tokens.font_weight_medium};
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.error_hover};
                        border-color: {tokens.error_hover};
                    }}
                """
            else:  # default
                return f"""
                    QPushButton {{
                        background-color: {tokens.interactive_hover};
                        border: 1px solid {tokens.border_default};
                        border-radius: {tokens.radius_md};
                        padding: {tokens.space_2} {tokens.space_4};
                        color: {tokens.text_primary};
                        font-weight: {tokens.font_weight_medium};
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.interactive_active};
                        border-color: {tokens.border_strong};
                    }}
                    QPushButton:pressed {{
                        background-color: {tokens.interactive_active};
                    }}
                    QPushButton:disabled {{
                        background-color: {tokens.interactive_disabled_bg};
                        color: {tokens.interactive_disabled_text};
                        border-color: {tokens.border_subtle};
                    }}
                """

        return self._get_cached_style(f"button_{variant}", generate)

    def get_input_style(self) -> str:
        """Get pre-computed input field style - CACHED."""

        def generate():
            tokens = self.tokens
            return f"""
                QLineEdit {{
                    background-color: {tokens.surface_card};
                    border: 1px solid {tokens.border_default};
                    border-radius: {tokens.radius_base};
                    padding: {tokens.space_2} {tokens.space_3};
                    min-height: {tokens.size_input_height};
                    color: {tokens.text_primary};
                    font-size: {tokens.font_size_base};
                    selection-background-color: {tokens.primary_subtle};
                }}
                QLineEdit:hover {{
                    border-color: {tokens.border_strong};
                }}
                QLineEdit:focus {{
                    border-color: {tokens.border_focus};
                }}
                QLineEdit:disabled {{
                    background-color: {tokens.interactive_disabled_bg};
                    color: {tokens.interactive_disabled_text};
                }}
            """

        return self._get_cached_style("input", generate)

    def get_label_style(self, variant: str = "default") -> str:
        """Get pre-computed label style - CACHED."""

        def generate():
            tokens = self.tokens

            if variant == "heading":
                return f"""
                    QLabel {{
                        color: {tokens.text_primary};
                        font-size: {tokens.font_size_lg};
                        font-weight: {tokens.font_weight_semibold};
                        background: transparent;
                    }}
                """
            elif variant == "secondary":
                return f"""
                    QLabel {{
                        color: {tokens.text_secondary};
                        font-size: {tokens.font_size_base};
                        background: transparent;
                    }}
                """
            elif variant == "muted":
                return f"""
                    QLabel {{
                        color: {tokens.text_muted};
                        font-size: {tokens.font_size_sm};
                        background: transparent;
                    }}
                """
            else:  # default
                return f"""
                    QLabel {{
                        color: {tokens.text_primary};
                        font-size: {tokens.font_size_base};
                        background: transparent;
                    }}
                """

        return self._get_cached_style(f"label_{variant}", generate)

    def get_frame_style(self, variant: str = "default") -> str:
        """Get pre-computed frame style - CACHED."""

        def generate():
            tokens = self.tokens

            if variant == "card":
                return f"""
                    QFrame {{
                        background-color: {tokens.surface_card};
                        border: 1px solid {tokens.border_default};
                        border-radius: {tokens.radius_lg};
                        padding: {tokens.space_4};
                    }}
                """
            elif variant == "panel":
                return f"""
                    QFrame {{
                        background-color: {tokens.surface_panel};
                        border: none;
                    }}
                """
            elif variant == "elevated":
                return f"""
                    QFrame {{
                        background-color: {tokens.surface_elevated};
                        border: 1px solid {tokens.border_subtle};
                        border-radius: {tokens.radius_lg};
                    }}
                """
            else:  # default
                return f"""
                    QFrame {{
                        background-color: transparent;
                        border: none;
                    }}
                """

        return self._get_cached_style(f"frame_{variant}", generate)

    def get_scrollbar_style(self) -> str:
        """Get pre-computed scrollbar style - CACHED."""

        def generate():
            tokens = self.tokens
            return f"""
                QScrollBar:vertical {{
                    background: {tokens.scrollbar_track};
                    width: 8px;
                    margin: {tokens.space_1} {tokens.space_1};
                    border-radius: {tokens.radius_sm};
                }}
                QScrollBar::handle:vertical {{
                    background: {tokens.scrollbar_thumb};
                    border-radius: {tokens.radius_sm};
                    min-height: {tokens.space_6};
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {tokens.scrollbar_thumb_hover};
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical,
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {{
                    background: none;
                    height: 0;
                    border: none;
                }}
                QScrollBar:horizontal {{
                    background: {tokens.scrollbar_track};
                    height: 8px;
                    margin: {tokens.space_1} {tokens.space_1};
                    border-radius: {tokens.radius_sm};
                }}
                QScrollBar::handle:horizontal {{
                    background: {tokens.scrollbar_thumb};
                    border-radius: {tokens.radius_sm};
                    min-width: {tokens.space_6};
                }}
                QScrollBar::handle:horizontal:hover {{
                    background: {tokens.scrollbar_thumb_hover};
                }}
                QScrollBar::add-line:horizontal,
                QScrollBar::sub-line:horizontal,
                QScrollBar::add-page:horizontal,
                QScrollBar::sub-page:horizontal {{
                    background: none;
                    width: 0;
                    border: none;
                }}
            """

        return self._get_cached_style("scrollbar", generate)

    def get_tooltip_style(self) -> str:
        """Get pre-computed tooltip style - CACHED."""

        def generate():
            tokens = self.tokens
            return f"""
                QToolTip {{
                    background-color: {tokens.tooltip_bg};
                    color: {tokens.tooltip_text};
                    border: 1px solid {tokens.tooltip_border};
                    border-radius: {tokens.radius_base};
                    padding: {tokens.space_2} {tokens.space_3};
                    font-size: {tokens.font_size_sm};
                }}
            """

        return self._get_cached_style("tooltip", generate)

    def get_list_widget_style(self) -> str:
        """Get pre-computed list widget style - CACHED."""

        def generate():
            tokens = self.tokens
            return f"""
                QListWidget {{
                    background: transparent;
                    border: none;
                    outline: none;
                }}
                QListWidget::item {{
                    padding: {tokens.space_2} {tokens.space_3};
                    border-radius: {tokens.radius_base};
                    margin: 2px 4px;
                }}
                QListWidget::item:hover {{
                    background-color: {tokens.interactive_hover};
                }}
                QListWidget::item:selected {{
                    background-color: {tokens.interactive_selected_bg};
                    color: {tokens.interactive_selected_text};
                }}
            """

        return self._get_cached_style("list_widget", generate)

    def get_status_badge_style(self, status: str) -> str:
        """Get pre-computed status badge style."""
        color = self.get_status_color(status)
        bg_color = self.get_status_bg_color(status)
        tokens = self.tokens

        return f"""
            QLabel {{
                background-color: {bg_color};
                color: {color};
                padding: {tokens.space_1} {tokens.space_2};
                border-radius: {tokens.radius_full};
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_medium};
            }}
        """


# =========================================================================
# Factory functions
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
