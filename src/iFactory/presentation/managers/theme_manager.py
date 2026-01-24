"""
Theme Manager - OPTIMIZED with Pre-compiled Regex and Better Caching.
"""

from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import ClassVar, Dict

logger = logging.getLogger(__name__)


class ThemeManager:
    """
    Theme Manager - OPTIMIZED.

    Optimizations:
    1. Pre-compiled regex pattern (class-level)
    2. Merged variable cache
    3. Faster substitution with dict lookup
    """

    VARIABLE_PATTERN: ClassVar[re.Pattern] = re.compile("\\${([A-Za-z0-9_.-]+)}")
    __slots__ = (
        "_base",
        "_vars",
        "_page_svg",
        "_cache",
        "_current_mode",
        "_merged_cache",
    )

    def __init__(self, base_path: Path | str, vars_path: Path | str) -> None:
        """Initialize theme manager with file paths."""
        (base_path, vars_path) = (Path(base_path), Path(vars_path))
        if not base_path.exists():
            raise FileNotFoundError(f"Theme base not found: {base_path}")
        if not vars_path.exists():
            raise FileNotFoundError(f"Theme variables not found: {vars_path}")
        try:
            self._base = base_path.read_text(encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Failed to load theme base: {e}") from e
        try:
            self._vars = json.loads(vars_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to load theme variables: {e}") from e
        self._page_svg: Dict[str, Dict[str, str]] = (
            self._vars.get("pageSvg", {}) if isinstance(self._vars, dict) else {}
        )
        self._cache: Dict[str, str] = {}
        self._merged_cache: Dict[str, Dict[str, str]] = {}
        self._current_mode: str = "light"
        self._prebuild_merged_cache()
        logger.info("ThemeManager initialized")

    def _prebuild_merged_cache(self) -> None:
        """Pre-build merged variable dictionaries for each mode."""
        common = self._vars.get("common", {})
        for mode in ("light", "dark"):
            mode_vars = self._vars.get(mode, {})
            self._merged_cache[mode] = {**common, **mode_vars}

    def render(self, mode: str) -> str:
        """
        Render stylesheet - OPTIMIZED.

        Uses pre-merged variable cache for faster substitution.
        """
        mode = "dark" if mode == "dark" else "light"
        if mode in self._cache:
            return self._cache[mode]
        merged = self._merged_cache.get(mode)
        if merged is None:
            merged = {**self._vars.get("common", {}), **self._vars.get(mode, {})}

        def replacer(match: re.Match) -> str:
            return merged.get(match.group(1), "")

        result = self.VARIABLE_PATTERN.sub(replacer, self._base)
        self._cache[mode] = result
        return result

    def set_theme(self, mode: str) -> str:
        """Set current theme and return stylesheet."""
        self._current_mode = "dark" if mode == "dark" else "light"
        return self.render(self._current_mode)

    @property
    def mode(self) -> str:
        """Get currently active theme mode."""
        return self._current_mode

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark mode."""
        return self._current_mode == "dark"

    def get_page_svg(self, frame_name: str, mode: str = "light") -> str:
        """Get SVG path for a frame and theme."""
        config = self._page_svg.get(frame_name, {})
        return config.get(mode, config.get("light", ""))

    def get_variable(self, name: str, mode: str = "light") -> str:
        """Get value of a specific CSS variable."""
        merged = self._merged_cache.get(mode)
        if merged:
            return merged.get(name, "")
        mode_vars = self._vars.get(mode, {})
        common_vars = self._vars.get("common", {})
        return mode_vars.get(name) or common_vars.get(name, "")

    def get_all_variables(self, mode: str = "light") -> Dict[str, str]:
        """Get all CSS variables for a theme mode."""
        return self._merged_cache.get(mode, {}).copy()

    @property
    def available_modes(self) -> list[str]:
        """Get list of available theme modes."""
        modes = []
        for key in self._vars:
            if key not in ("common", "pageSvg", "icons", "iconAlias"):
                modes.append(key)
        return modes or ["light", "dark"]

    def clear_cache(self) -> None:
        """Clear stylesheet cache."""
        self._cache.clear()

    def reload(
        self, base_path: Path | str | None = None, vars_path: Path | str | None = None
    ) -> None:
        """Reload theme files from disk."""
        if base_path:
            self._base = Path(base_path).read_text(encoding="utf-8")
        if vars_path:
            self._vars = json.loads(Path(vars_path).read_text(encoding="utf-8"))
            self._page_svg = (
                self._vars.get("pageSvg", {}) if isinstance(self._vars, dict) else {}
            )
            self._prebuild_merged_cache()
        self.clear_cache()
        logger.info("Theme reloaded")
