"""
Device Visualization and Management - Canvas-based approach.

Refactored to use Application layer for status mapping.
Domain imports removed to maintain Clean Architecture.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QFrame, QToolTip, QWidget

try:
    from PySide6.QtSvg import QSvgRenderer

    _HAS_SVG = True
except ImportError:
    QSvgRenderer = None
    _HAS_SVG = False

logger = logging.getLogger(__name__)

_global_ui_mapper = None


def _get_ui_mapper():
    """Get global UI mapper for status mapping."""
    global _global_ui_mapper
    if _global_ui_mapper is None:
        from iFactory.application.services.status_ui_mapper import StatusUIMapper
        _global_ui_mapper = StatusUIMapper()
    return _global_ui_mapper
__all__ = [
    "DeviceData",
    "DeviceSvgWidget",
    "DeviceLayoutManager",
    "ScalableSvgWidget",
    "DeviceStatusProvider",
]


def _find_config_path() -> Path:
    candidates = [
        Path.cwd() / "data" / "device_positions.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


DEVICE_CONFIG_PATH = _find_config_path()


class DeviceStatusProvider(Protocol):
    def get_device_data(self, device_id: str) -> Optional[Dict[str, Any]]: ...


@dataclass
class DeviceData:
    """Device display data and configuration."""

    device_id: str
    name: str
    status: str = "unknown"
    status_code: str = "0"
    x_pct: float = 0.0
    y_pct: float = 0.0
    base_width: int = 60
    base_height: int = 60
    label_text: str = ""
    label_position: str = "none"
    label_spacing: int = 0
    label_font_size: int = 11
    label_color: str = "#333333"
    label_color_dark: str = "#ffffff"
    image_light: str = ""
    image_dark: str = ""
    theme: str = field(default="light", repr=False)
    svg_renderer: Optional[Any] = field(default=None, repr=False)
    icon_rect: QRect = field(default_factory=QRect, repr=False)
    label_rect: QRect = field(default_factory=QRect, repr=False)
    bounds: QRect = field(default_factory=QRect, repr=False)

    def load_svg(self) -> None:
        if not _HAS_SVG or QSvgRenderer is None:
            return
        path = self.image_dark if self.theme == "dark" else self.image_light
        self.svg_renderer = None
        if path:
            try:
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    self.svg_renderer = renderer
                elif self.theme == "dark" and self.image_light:
                    fallback = QSvgRenderer(self.image_light)
                    if fallback.isValid():
                        self.svg_renderer = fallback
            except Exception as e:
                logger.warning(f"Failed to load SVG for {self.device_id}: {e}")

    def set_theme(self, theme: str) -> None:
        self.theme = "dark" if theme == "dark" else "light"
        self.load_svg()

    def set_status_from_code(self, code: Any) -> None:
        self.status_code = str(code)
        # Use Application layer UI mapper for display
        ui_mapper = _get_ui_mapper()
        self.status = ui_mapper.get_display_text(self.status_code).lower()

    def get_status_color(self) -> QColor:
        # Use Application layer UI mapper for color
        ui_mapper = _get_ui_mapper()
        color_hex = ui_mapper.get_color(self.status_code, self.theme)
        return QColor(color_hex)

    def get_label_color(self) -> QColor:
        color = self.label_color_dark if self.theme == "dark" else self.label_color
        return QColor(color)

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "DeviceData":
        return cls(
            device_id=cfg.get("id", ""),
            name=cfg.get("name", cfg.get("id", "")),
            x_pct=cfg.get("x_percent", 0),
            y_pct=cfg.get("y_percent", 0),
            base_width=cfg.get("width", 60),
            base_height=cfg.get("height", 60),
            label_text=cfg.get("label_text", ""),
            label_position=cfg.get("label_position", "none"),
            label_spacing=cfg.get("label_spacing", 0),
            label_font_size=cfg.get("label_font_size", 11),
            label_color=cfg.get("label_color", "#333333"),
            label_color_dark=cfg.get("label_color_dark", "#ffffff"),
            image_light=cfg.get("image", ""),
            image_dark=cfg.get("image_dark", cfg.get("image", "")),
        )

    def to_config(self) -> Dict[str, Any]:
        return {
            "id": self.device_id,
            "name": self.name,
            "x_percent": round(self.x_pct, 2),
            "y_percent": round(self.y_pct, 2),
            "width": self.base_width,
            "height": self.base_height,
            "label_text": self.label_text,
            "label_position": self.label_position,
            "label_spacing": self.label_spacing,
            "label_font_size": self.label_font_size,
            "label_color": self.label_color,
            "label_color_dark": self.label_color_dark,
            "image": self.image_light,
            "image_dark": self.image_dark,
        }


class DeviceSvgWidget(QWidget):
    """Interactive widget displaying ALL devices on a single canvas."""

    device_clicked = Signal(str, str)
    device_right_clicked = Signal(str, str, object)
    device_moved = Signal(str, float, float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._bg_svg: Optional[Any] = None
        self._content_rect = QRect()
        self._devices: List[DeviceData] = []
        self._hover_device: Optional[DeviceData] = None
        self._drag_device: Optional[DeviceData] = None
        self._edit_mode = False
        self._theme = "light"
        self._ref_width = 1200
        self._ref_height = 600
        self._min_scale = 0.5
        self._max_scale = 1.5
        self._hide_labels_below = 0.6
        self._cached_scale = 1.0
        self._needs_recalc = True
        self._tooltip_callback: Optional[Callable[[str], Optional[Dict]]] = None
        self._in_paint = False
        self._in_mouse = False
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(16)
        self._update_timer.timeout.connect(self._do_update)
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(150)
        self._tooltip_timer.timeout.connect(self._show_tooltip)
        self._pending_tooltip: Optional[DeviceData] = None
        self._tooltip_pos = QPoint()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

    def set_scale_config(self, ref_w: int, ref_h: int, min_s: float, max_s: float) -> None:
        self._ref_width = ref_w
        self._ref_height = ref_h
        self._min_scale = min_s
        self._max_scale = max_s
        self._needs_recalc = True
        self._schedule_update()

    def set_tooltip_callback(self, callback: Optional[Callable[[str], Optional[Dict]]]) -> None:
        """Set callback for tooltip data."""
        self._tooltip_callback = callback
        logger.debug(f"[DeviceSvgWidget] Tooltip callback set: {callback is not None}")

    def load_svg(self, path: str) -> None:
        self._bg_svg = None
        if _HAS_SVG and QSvgRenderer and path:
            try:
                renderer = QSvgRenderer(path)
                if renderer.isValid():
                    self._bg_svg = renderer
            except Exception as e:
                logger.warning(f"Failed to load background SVG: {e}")
        self._needs_recalc = True
        self._schedule_update()

    def set_devices(self, devices: List[DeviceData]) -> None:
        self._devices = devices
        self._needs_recalc = True
        self._schedule_update()

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"
        for device in self._devices:
            device.set_theme(self._theme)
        self._schedule_update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        cursor = Qt.CursorShape.SizeAllCursor if enabled else Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)

    def _calc_scale(self) -> float:
        if self._content_rect.isEmpty() or self._ref_width <= 0:
            return 1.0
        scale = min(
            self._content_rect.width() / self._ref_width,
            self._content_rect.height() / self._ref_height,
        )
        return max(self._min_scale, min(self._max_scale, scale))

    def _calc_content_rect(self) -> None:
        if not self._bg_svg or not self._bg_svg.isValid():
            self._content_rect = self.rect()
            return
        svg_size = self._bg_svg.defaultSize()
        if svg_size.isValid() and svg_size.width() > 0:
            scale = min(self.width() / svg_size.width(), self.height() / svg_size.height())
            w = int(svg_size.width() * scale)
            h = int(svg_size.height() * scale)
            x = (self.width() - w) // 2
            y = (self.height() - h) // 2
            self._content_rect = QRect(x, y, w, h)
        else:
            self._content_rect = self.rect()
        self._cached_scale = self._calc_scale()

    def _calc_device_rects(self, device: DeviceData, scale: float) -> None:
        icon_w = max(8, int(device.base_width * scale))
        icon_h = max(8, int(device.base_height * scale))
        cx = self._content_rect.x() + int(self._content_rect.width() * device.x_pct / 100)
        cy = self._content_rect.y() + int(self._content_rect.height() * device.y_pct / 100)
        show_label = device.label_text and device.label_position != "none" and (scale >= self._hide_labels_below)
        if not show_label:
            device.icon_rect = QRect(cx - icon_w // 2, cy - icon_h // 2, icon_w, icon_h)
            device.label_rect = QRect()
            device.bounds = device.icon_rect
            return
        font = QFont("Segoe UI")
        font.setPixelSize(max(6, int(device.label_font_size * scale)))
        font.setBold(True)
        fm = QFontMetrics(font)
        label_w = fm.horizontalAdvance(device.label_text) + int(2 * scale)
        label_h = fm.height()
        spacing = int(device.label_spacing * scale)
        pos = device.label_position
        if pos == "top":
            icon_y = cy - icon_h // 2 + label_h // 2 + spacing // 2
            device.icon_rect = QRect(cx - icon_w // 2, icon_y, icon_w, icon_h)
            device.label_rect = QRect(cx - label_w // 2, icon_y - spacing - label_h, label_w, label_h)
        elif pos == "bottom":
            icon_y = cy - icon_h // 2 - label_h // 2 - spacing // 2
            device.icon_rect = QRect(cx - icon_w // 2, icon_y, icon_w, icon_h)
            device.label_rect = QRect(cx - label_w // 2, icon_y + icon_h + spacing, label_w, label_h)
        elif pos == "left":
            icon_x = cx - icon_w // 2 + label_w // 2 + spacing // 2
            device.icon_rect = QRect(icon_x, cy - icon_h // 2, icon_w, icon_h)
            device.label_rect = QRect(icon_x - spacing - label_w, cy - label_h // 2, label_w, label_h)
        elif pos == "right":
            icon_x = cx - icon_w // 2 - label_w // 2 - spacing // 2
            device.icon_rect = QRect(icon_x, cy - icon_h // 2, icon_w, icon_h)
            device.label_rect = QRect(icon_x + icon_w + spacing, cy - label_h // 2, label_w, label_h)
        else:
            device.icon_rect = QRect(cx - icon_w // 2, cy - icon_h // 2, icon_w, icon_h)
            device.label_rect = QRect()
        if not device.label_rect.isNull():
            device.bounds = device.icon_rect.united(device.label_rect)
        else:
            device.bounds = device.icon_rect

    def _recalc_all(self) -> None:
        self._calc_content_rect()
        for device in self._devices:
            self._calc_device_rects(device, self._cached_scale)
        self._needs_recalc = False

    def paintEvent(self, event) -> None:
        if self._in_paint:
            return
        self._in_paint = True
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self._needs_recalc:
                self._recalc_all()
            if self._bg_svg and self._bg_svg.isValid():
                self._bg_svg.render(painter, QRectF(self._content_rect))
            for device in self._devices:
                self._draw_device(painter, device, device is self._hover_device)
            painter.end()
        finally:
            self._in_paint = False

    def _draw_device(self, painter: QPainter, device: DeviceData, hovered: bool) -> None:
        icon_rect = device.icon_rect
        if icon_rect.isNull() or icon_rect.width() < 1:
            return
        corner_r = max(2, min(icon_rect.width(), icon_rect.height()) // 10)
        painter.setBrush(device.get_status_color())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(icon_rect, corner_r, corner_r)
        if device.svg_renderer and device.svg_renderer.isValid():
            margin = max(2, min(icon_rect.width(), icon_rect.height()) // 8)
            svg_rect = icon_rect.adjusted(margin, margin, -margin, -margin)
            if svg_rect.width() > 2 and svg_rect.height() > 2:
                svg_size = device.svg_renderer.defaultSize()
                if svg_size.isValid() and svg_size.width() > 0:
                    scale = min(
                        svg_rect.width() / svg_size.width(),
                        svg_rect.height() / svg_size.height(),
                    )
                    target_w = max(1, int(svg_size.width() * scale))
                    target_h = max(1, int(svg_size.height() * scale))
                    target_rect = QRectF(
                        svg_rect.x() + (svg_rect.width() - target_w) // 2,
                        svg_rect.y() + (svg_rect.height() - target_h) // 2,
                        target_w,
                        target_h,
                    )
                    device.svg_renderer.render(painter, target_rect)
        if hovered:
            painter.setPen(QPen(QColor("#ffffff"), max(1, int(2 * self._cached_scale))))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(icon_rect.adjusted(1, 1, -1, -1), corner_r, corner_r)
        label_rect = device.label_rect
        if not label_rect.isNull() and device.label_text:
            if self._cached_scale >= self._hide_labels_below:
                font = QFont("Segoe UI")
                font.setPixelSize(max(6, int(device.label_font_size * self._cached_scale)))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor(0, 0, 0, 60))
                painter.drawText(
                    label_rect.adjusted(1, 1, 1, 1),
                    Qt.AlignmentFlag.AlignCenter,
                    device.label_text,
                )
                painter.setPen(device.get_label_color())
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, device.label_text)

    def resizeEvent(self, event) -> None:
        self._needs_recalc = True
        super().resizeEvent(event)

    def _find_device_at(self, pos: QPoint) -> Optional[DeviceData]:
        for device in reversed(self._devices):
            if device.bounds.contains(pos):
                return device
        return None

    def mouseMoveEvent(self, event) -> None:
        if self._in_mouse:
            return
        self._in_mouse = True
        try:
            pos = event.pos()
            if self._drag_device and self._edit_mode:
                if self._content_rect.width() > 0:
                    x_pct = (pos.x() - self._content_rect.x()) / self._content_rect.width() * 100
                    y_pct = (pos.y() - self._content_rect.y()) / self._content_rect.height() * 100
                    self._drag_device.x_pct = max(0, min(100, x_pct))
                    self._drag_device.y_pct = max(0, min(100, y_pct))
                    self._calc_device_rects(self._drag_device, self._cached_scale)
                    self._schedule_update()
            else:
                device = self._find_device_at(pos)
                if device != self._hover_device:
                    self._hover_device = device
                    if device:
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        self._pending_tooltip = device
                        self._tooltip_pos = event.globalPosition().toPoint()
                        if not self._tooltip_timer.isActive():
                            self._tooltip_timer.start()
                    else:
                        cursor = Qt.CursorShape.SizeAllCursor if self._edit_mode else Qt.CursorShape.ArrowCursor
                        self.setCursor(cursor)
                        self._tooltip_timer.stop()
                        self._pending_tooltip = None
                        QToolTip.hideText()
                    self._schedule_update()
        finally:
            self._in_mouse = False

    def mousePressEvent(self, event) -> None:
        device = self._find_device_at(event.pos())
        if not device:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._edit_mode:
                self._drag_device = device
            else:
                logger.debug(f"[DeviceSvgWidget] Click: {device.device_id}")
                self.device_clicked.emit(device.device_id, device.name)
        elif event.button() == Qt.MouseButton.RightButton:
            global_pos = self.mapToGlobal(event.pos())
            self.device_right_clicked.emit(device.device_id, device.name, global_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_device:
            self.device_moved.emit(
                self._drag_device.device_id,
                self._drag_device.x_pct,
                self._drag_device.y_pct,
            )
            self._drag_device = None

    def leaveEvent(self, event) -> None:
        if self._hover_device:
            self._hover_device = None
            self._tooltip_timer.stop()
            QToolTip.hideText()
            self._schedule_update()

    def _show_tooltip(self) -> None:
        """Show tooltip for pending device with proper data format handling."""
        if not self._pending_tooltip:
            return
        device = self._pending_tooltip
        lines = [
            f"<b>{device.label_text or device.device_id}</b>",
            f"<i>{device.name}</i>",
            "<hr style='margin: 4px 0;'>",
        ]
        db_status_code = None
        db_status_name = None
        has_data = False
        if self._tooltip_callback:
            try:
                data = self._tooltip_callback(device.device_id)
                if data:
                    has_data = True
                    db_status_code = self._extract_status_code(data)
                    db_status_name = self._extract_status_name(data)
                    if db_status_code is not None:
                        device.set_status_from_code(db_status_code)
                        self._schedule_update()
                    if db_status_code is not None:
                        # Use Application layer UI mapper for display
                        ui_mapper = _get_ui_mapper()
                        display = db_status_name.upper() if db_status_name else ui_mapper.get_display_text(str(db_status_code))
                        color = ui_mapper.get_color(str(db_status_code), self._theme)
                        lines.append(f"<b>Status:</b> <span style='color:{color};'>●</span> {display}")
                    batch = self._extract_field(data, ["MATERIAL_BATCH", "material_batch"])
                    if batch:
                        lines.append(f"<b>Material:</b> {batch}")
                    feeding_time = self._extract_field(data, ["FEEDING_TIME", "feeding_time"])
                    if feeding_time:
                        lines.append(f"<b>Fed at:</b> {feeding_time}")
                    last_update = data.get("last_update")
                    if last_update:
                        if hasattr(last_update, "strftime"):
                            last_update = last_update.strftime("%H:%M:%S")
                        lines.append(f"<b>Updated:</b> {last_update}")
            except Exception as e:
                logger.error(f"[Tooltip] Callback error for {device.device_id}: {e}")
                lines.append("<span style='color:red;'>Error loading data</span>")
        lines.append("<hr style='margin: 4px 0;'>")
        # Use Application layer UI mapper for canvas status display
        ui_mapper = _get_ui_mapper()
        canvas_display = ui_mapper.get_display_text(str(device.status_code))
        lines.append(f"<small>Canvas: {canvas_display} (code: {device.status_code})</small>")
        if has_data and db_status_code is not None:
            db_code_str = str(db_status_code).strip()
            canvas_code_str = str(device.status_code).strip()
            if db_code_str != canvas_code_str:
                lines.append(f"<span style='color: #FF9800; font-weight: bold;'>⚠ MISMATCH: DB={db_code_str} ≠ Canvas={canvas_code_str}</span>")
        elif not has_data:
            lines.insert(3, "<span style='color: #FF9800;'>⚠ No cached data available</span>")
        QToolTip.showText(self._tooltip_pos, "<br>".join(lines), self, QRect(), 5000)

    def _extract_status_code(self, status_data: Any) -> Optional[str]:
        """
        Extract status code from various input formats.
        Delegates validation to Domain Enum if possible.
        """
        if status_data is None:
            return None
        if isinstance(status_data, (str, int)):
            return str(status_data)
        if isinstance(status_data, dict):
            for key in ("status_code", "status", "EQUIP_STATUS", "equip_status"):
                if value := status_data.get(key):
                    if isinstance(value, dict):
                        continue
                    return str(value)
        if hasattr(status_data, "status_code"):
            return str(status_data.status_code)
        return None

    def _extract_status_name(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract status name from data."""
        status_data = data.get("status") if isinstance(data.get("status"), dict) else {}
        return status_data.get("status_name") or data.get("status_name")

    def _extract_color(self, data: Dict[str, Any]) -> str:
        """
        Extract color from data.
        Note: This is legacy. Prefer Domain Enum colors.
        """
        status_data = data.get("status") if isinstance(data.get("status"), dict) else {}
        # If color is provided in DB data, use it, otherwise default
        return data.get("status_color") or status_data.get("status_color") or "#808080"

    def _extract_field(self, data: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        """Extract field from data trying multiple key names."""
        input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
        for key in keys:
            if input_data.get(key):
                return input_data[key]
            if data.get(key):
                return data[key]
        return None

    def _schedule_update(self) -> None:
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _do_update(self) -> None:
        if not self._in_paint:
            self.update()

    def get_content_rect(self) -> QRect:
        return self._content_rect


class DeviceConfigLoader(QObject):
    """Manages device layout across multiple frames."""

    def __init__(self, config_path: Optional[Path] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._path = config_path or DEVICE_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._frames: Dict[str, QFrame] = {}
        self._widgets: Dict[str, DeviceSvgWidget] = {}
        self._devices: Dict[str, List[DeviceData]] = {}
        self._edit_mode = False
        self._theme = "light"
        self._click_callback: Optional[Callable[[str, str], None]] = None
        self._context_callback: Optional[Callable[[str, str, Any], None]] = None
        self._tooltip_callback: Optional[Callable[[str], Optional[Dict]]] = None
        self._in_event = False
        self._resizing: Dict[str, bool] = {}
        self._load_config()

    def _load_config(self) -> None:
        try:
            if self._path.exists():
                self._config = json.loads(self._path.read_text(encoding="utf-8"))
                logger.info(f"Loaded device config from {self._path}")
        except Exception as e:
            logger.error(f"Failed to load device config: {e}")
            self._config = {}

    def _save_config(self) -> None:
        try:
            for name, devices in self._devices.items():
                if name in self._config:
                    for device in devices:
                        for device_cfg in self._config[name].get("devices", []):
                            if device_cfg.get("id") == device.device_id:
                                device_cfg["x_percent"] = round(device.x_pct, 2)
                                device_cfg["y_percent"] = round(device.y_pct, 2)
            self._path.write_text(json.dumps(self._config, indent=4), encoding="utf-8")
            logger.info(f"Saved device config to {self._path}")
        except Exception as e:
            logger.error(f"Failed to save device config: {e}")

    def set_click_callback(self, callback: Callable[[str, str], None]) -> None:
        self._click_callback = callback

    def set_context_menu_callback(self, callback: Callable[[str, str, Any], None]) -> None:
        self._context_callback = callback

    def set_tooltip_callback(self, callback: Callable[[str], Optional[Dict]]) -> None:
        """Set callback for tooltip data - propagates to all widgets."""
        self._tooltip_callback = callback
        logger.info(f"[DeviceLayoutManager] Tooltip callback set: {callback is not None}")
        for name, widget in self._widgets.items():
            widget.set_tooltip_callback(callback)
            logger.debug(f"[DeviceLayoutManager] Updated tooltip callback for {name}")

    def _extract_status_code(self, status_data: Any) -> Optional[str]:
        """
        Extract status code from various input formats.
        Delegates validation to Domain Enum if possible.
        """
        if status_data is None:
            return None
        if isinstance(status_data, (str, int)):
            return str(status_data)
        if isinstance(status_data, dict):
            for key in ("status_code", "status", "EQUIP_STATUS", "equip_status"):
                if value := status_data.get(key):
                    if isinstance(value, dict):
                        continue
                    return str(value)
        if hasattr(status_data, "status_code"):
            return str(status_data.status_code)
        return None

    def register_frame(self, name: str, frame: QFrame, svg_widget: Optional[DeviceSvgWidget] = None) -> None:
        self._frames[name] = frame
        widget = svg_widget or DeviceSvgWidget(frame)
        widget.setGeometry(0, 0, frame.width(), frame.height())
        self._widgets[name] = widget
        self._resizing[name] = False
        frame_cfg = self._config.get(name, {})
        widget.set_scale_config(
            frame_cfg.get("ref_width", 1200),
            frame_cfg.get("ref_height", 600),
            frame_cfg.get("min_scale", 0.5),
            frame_cfg.get("max_scale", 1.5),
        )
        devices = [DeviceData.from_config(device_cfg) for device_cfg in frame_cfg.get("devices", [])]
        for device in devices:
            device.set_theme(self._theme)
        self._devices[name] = devices
        widget.set_devices(devices)
        widget.set_theme(self._theme)
        if self._tooltip_callback:
            widget.set_tooltip_callback(self._tooltip_callback)
            logger.debug(f"[DeviceLayoutManager] Set tooltip callback for new frame {name}")
        widget.device_clicked.connect(lambda did, dn: self._on_device_clicked(did, dn))
        widget.device_right_clicked.connect(lambda did, dn, pos: self._on_device_right_clicked(did, dn, pos))
        widget.device_moved.connect(lambda *args: self._on_device_moved())
        frame.installEventFilter(self)
        widget.show()
        logger.debug(f"Registered frame '{name}' with {len(devices)} devices")

    def _on_device_clicked(self, device_id: str, device_name: str) -> None:
        logger.debug(f"[DeviceLayoutManager] Device clicked: {device_id}")
        if self._click_callback:
            self._click_callback(device_id, device_name)

    def _on_device_right_clicked(self, device_id: str, device_name: str, pos: Any) -> None:
        if self._context_callback:
            self._context_callback(device_id, device_name, pos)
        else:
            logger.debug(f"[DeviceLayoutManager] Context menu callback not set for {device_id}")

    def _on_device_moved(self) -> None:
        if self._edit_mode:
            self._save_config()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Resize or self._in_event:
            return False
        self._in_event = True
        try:
            name = next((n for (n, f) in self._frames.items() if f is obj), None)
            if name and (not self._resizing.get(name)):
                self._resizing[name] = True
                widget = self._widgets[name]
                frame = self._frames[name]
                if widget.width() != frame.width() or widget.height() != frame.height():
                    widget.setFixedSize(frame.width(), frame.height())
                    widget.move(0, 0)
                    widget._needs_recalc = True
                self._resizing[name] = False
        finally:
            self._in_event = False
        return False

    def load_svg_for_frame(self, name: str, path: str) -> None:
        if name in self._widgets:
            self._widgets[name].load_svg(path)

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"
        for widget in self._widgets.values():
            widget.set_theme(self._theme)

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        for widget in self._widgets.values():
            widget.set_edit_mode(enabled)

    def toggle_edit_mode(self) -> bool:
        self.set_edit_mode(not self._edit_mode)
        return self._edit_mode

    @property
    def is_edit_mode(self) -> bool:
        return self._edit_mode

    def update_device_status(self, device_id: str, status: str, frame: Optional[str] = None) -> None:
        frames_to_check = [frame] if frame else list(self._devices.keys())
        for frame_name in frames_to_check:
            for device in self._devices.get(frame_name, []):
                if device.device_id == device_id:
                    # Use Application layer UI mapper for status display
                    device.set_status_from_code(status)
                    if frame_name in self._widgets:
                        self._widgets[frame_name]._schedule_update()
                    return

    def update_all_status(self, status_dict: Dict[str, Any]) -> None:
        """
        Update status for multiple devices.
        Supports both legacy and new formats.
        """
        updated = 0
        for device_id, status_data in status_dict.items():
            status_code = self._extract_status_code(status_data)
            if status_code is not None:
                self.update_device_status(device_id, status_code)
                updated += 1
            else:
                logger.warning(f"[DeviceLayoutManager] Could not extract status for {device_id}: {type(status_data).__name__}")
        if updated > 0:
            logger.debug(f"[DeviceLayoutManager] Updated {updated} device statuses")

    def get_device(self, device_id: str) -> Optional[DeviceData]:
        for devices in self._devices.values():
            for device in devices:
                if device.device_id == device_id:
                    return device
        return None

    def get_all_device_ids(self) -> List[str]:
        return [device.device_id for devices in self._devices.values() for device in devices]

    def get_widget(self, name: str) -> Optional[DeviceSvgWidget]:
        return self._widgets.get(name)

    def refresh_all_widgets(self) -> None:
        for widget in self._widgets.values():
            widget._needs_recalc = True
            widget._schedule_update()

    def update_all_positions(self) -> None:
        self.refresh_all_widgets()


ScalableSvgWidget = DeviceSvgWidget
