"""
Icon Manager - Manages icon rendering and caching.

Provides theme-aware icon resolution with SVG support.
"""

from __future__ import annotations
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer

    HAS_SVG = True
except ImportError:
    HAS_SVG = False
    QSvgRenderer = None
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IconConfig:
    """
    Configuration for icon rendering.

    Attributes:
        pad: Padding in pixels around the icon content.
        scale: Scaling factor (1.0 = 100%).
    """

    pad: int = 2
    scale: float = 1.0

    def __post_init__(self) -> None:
        """
        Validate configuration values after initialization.

        Ensures padding is non-negative and scale is positive.
        """
        self.pad = max(0, self.pad)
        self.scale = max(0.01, self.scale)


class IconManager:
    """
    Manages icon rendering with theme support.

    Handles the resolution of icon paths based on the active theme,
    rendering SVG and raster images, and caching the resulting QPixmaps/QIcons.

    Features:
        - Theme-aware icon resolution (aliases).
        - SVG rendering with configurable scaling and padding.
        - LRU caching mechanism for performance.
        - Fallback to raster images if SVG support is unavailable.

    Example:
        icons = IconManager(vars_path="variables.json")
        icons.set_mode("dark")
        icon = icons.icon(":/icon/settings.svg", QSize(24, 24))
    """

    DEFAULT_CACHE_SIZE: int = 100
    DEFAULT_ICON_SIZE: QSize = QSize(24, 24)
    __slots__ = (
        "_vars",
        "_icon_configs",
        "_default_config",
        "_alias_all",
        "_alias",
        "_mode",
        "_max_cache_size",
        "_cache",
    )

    def __init__(
        self,
        vars_path: Path | str,
        max_cache_size: int = DEFAULT_CACHE_SIZE,
        initial_mode: str = "dark",
    ):
        """
        Initialize icon manager.

        Args:
            vars_path: Path to variables.json.
            max_cache_size: Maximum number of cached icons.

        Raises:
            FileNotFoundError: If variables file is not found.
            ValueError: If JSON is invalid.
        """
        vars_path = Path(vars_path)
        if not vars_path.exists():
            raise FileNotFoundError(f"Icon variables not found: {vars_path}")
        try:
            self._vars = json.loads(vars_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to load icon variables: {e}") from e
        self._icon_configs: dict[str, IconConfig] = {}
        self._default_config = IconConfig()
        self._parse_icon_configs()
        self._alias_all: dict[str, dict[str, str]] = self._vars.get("iconAlias", {})
        self._alias: dict[str, str] = {}
        self._mode = "dark" if initial_mode == "dark" else "light"
        self._alias = self._alias_all.get(self._mode, {})
        self._max_cache_size = max_cache_size
        self._cache: OrderedDict[tuple[str, int, int], QIcon] = OrderedDict()
        self.clear_cache()
        logger.info(
            f"IconManager initialized (cache size: {max_cache_size}, mode: {self._mode})"
        )

    def _parse_icon_configs(self) -> None:
        """Parse icon configurations from variables dictionary."""
        icon_cfg = self._vars.get("icons", {})
        if not isinstance(icon_cfg, dict):
            return
        if default := icon_cfg.get("_default"):
            if isinstance(default, dict):
                self._default_config = IconConfig(
                    pad=default.get("pad", 2), scale=default.get("scale", 1.0)
                )
        for key, value in icon_cfg.items():
            if key != "_default" and isinstance(value, dict):
                self._icon_configs[key] = IconConfig(
                    pad=value.get("pad", self._default_config.pad),
                    scale=value.get("scale", self._default_config.scale),
                )

    def set_mode(self, mode: str) -> None:
        """
        Set the current theme mode and update icon path aliases.

        Args:
            mode: Theme mode ("light" or "dark").
        """
        mode = "dark" if mode == "dark" else "light"
        if self._mode == mode:
            return
        self._mode = mode
        self._alias = self._alias_all.get(mode, {})
        self.clear_cache()

    @property
    def mode(self) -> str:
        """Get the current theme mode."""
        return self._mode

    def resolve(self, resource: str) -> str:
        """
        Resolve resource path using theme alias.

        Args:
            resource: The original resource path.

        Returns:
            The aliased path if available, otherwise the original.
        """
        return self._alias.get(resource, resource)

    def _get_config(self, resource: str) -> IconConfig:
        """Get icon configuration for a specific resource."""
        return self._icon_configs.get(resource, self._default_config)

    def icon(self, resource: str, size: Optional[QSize] = None) -> QIcon:
        """
        Get a rendered icon as QIcon.

        Args:
            resource: The resource path.
            size: The desired size (default: 24x24).

        Returns:
            A QIcon instance.
        """
        size = size or self.DEFAULT_ICON_SIZE
        resolved = self.resolve(resource)
        key = (resolved, size.width(), size.height())
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        config = self._get_config(resource)
        pixmap = self._render(resolved, size, config)
        icon = QIcon(pixmap)
        self._cache[key] = icon
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)
        return icon

    def pixmap(self, resource: str, size: Optional[QSize] = None) -> QPixmap:
        """
        Get a rendered icon as QPixmap.

        Args:
            resource: The resource path.
            size: The desired size (default: 24x24).

        Returns:
            A QPixmap instance.
        """
        size = size or self.DEFAULT_ICON_SIZE
        resolved = self.resolve(resource)
        return self._render(resolved, size, self._get_config(resource))

    def _render(self, resource: str, size: QSize, config: IconConfig) -> QPixmap:
        """
        Render the icon to a QPixmap.

        Args:
            resource: Path to the icon file.
            size: The target size of the pixmap.
            config: The IconConfig to use.

        Returns:
            The rendered QPixmap.
        """
        canvas = QPixmap(size)
        canvas.fill(Qt.GlobalColor.transparent)
        inner_w = max(1, size.width() - 2 * config.pad)
        inner_h = max(1, size.height() - 2 * config.pad)
        inner = QRect(config.pad, config.pad, inner_w, inner_h)
        target_rect = inner
        if config.scale != 1.0:
            sw = max(1, int(inner.width() * config.scale))
            sh = max(1, int(inner.height() * config.scale))
            scaled_rect = QRect(0, 0, sw, sh)
            canvas_rect = QRect(0, 0, size.width(), size.height())
            scaled_rect.moveCenter(canvas_rect.center())
            target_rect = scaled_rect
        else:
            canvas_rect = QRect(0, 0, size.width(), size.height())
            target_rect.moveCenter(canvas_rect.center())
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        try:
            if resource.lower().endswith(".svg") and HAS_SVG:
                self._render_svg(painter, resource, target_rect)
            else:
                self._render_raster(painter, resource, target_rect)
        except Exception as e:
            logger.warning(f"Icon render failed '{resource}': {e}")
        finally:
            painter.end()
        return canvas

    def _render_svg(self, painter: QPainter, path: str, rect: QRect) -> None:
        """
        Render SVG icon onto the painter.

        Handles scaling and aspect ratio preservation.
        """
        if not QSvgRenderer:
            return
        try:
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                return
            svg_size = renderer.defaultSize()
            if svg_size.isValid() and svg_size.width() > 0 and (svg_size.height() > 0):
                scale_factor = min(
                    rect.width() / svg_size.width(), rect.height() / svg_size.height()
                )
                tw = max(1, int(svg_size.width() * scale_factor))
                th = max(1, int(svg_size.height() * scale_factor))
                draw_rect = QRect(0, 0, tw, th)
                draw_rect.moveCenter(rect.center())
            else:
                draw_rect = rect
            renderer.render(painter, draw_rect)
        except Exception as e:
            logger.warning(f"SVG render error: {e}")

    def _render_raster(self, painter: QPainter, path: str, rect: QRect) -> None:
        """
        Render raster icon onto the painter.

        Scales the image to fit the target rect smoothly.
        """
        try:
            source = QPixmap(path)
            if source.isNull():
                return
            scaled = source.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            target = QRect(0, 0, scaled.width(), scaled.height())
            target.moveCenter(rect.center())
            painter.drawPixmap(target.topLeft(), scaled)
        except Exception as e:
            logger.warning(f"Raster render error: {e}")

    def clear_cache(self) -> None:
        """Clear the icon cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get current number of cached items."""
        return len(self._cache)

    def get_cache_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with size, max_size, and unique_resources count.
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_cache_size,
            "unique_resources": len({k[0] for k in self._cache.keys()}),
        }


__all__ = ["IconManager", "IconConfig"]
