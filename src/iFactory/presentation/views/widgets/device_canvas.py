# File: presentation/views/widgets/device_canvas.py
"""
Device Canvas - Factory floor visualization.

Uses ThemeService for device icons with automatic caching.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt, Signal, QTimer, QSize
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class DeviceIconItem(QGraphicsObject):
    """Individual device icon on the canvas."""

    def __init__(
        self,
        device_data: Dict[str, Any],
        ref_width: int,
        ref_height: int,
        parent_canvas: "DeviceCanvasWidget",
        theme_service: Optional["ThemeService"] = None,
    ):
        super().__init__()
        self.device_data = device_data
        self.equip_code = device_data["id"]
        self._parent_canvas = parent_canvas
        self._theme_service = theme_service

        self.w = device_data.get("width", 40)
        self.h = device_data.get("height", 40)
        self._padding = 2

        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height
        self.setPos(x, y)

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self._status_color = QColor("Transparent")
        self._is_hovered = False
        self._pixmap: Optional[QPixmap] = None
        self._is_dark = False

        # Click detection
        self._click_timer: Optional[QTimer] = None
        self._pending_single_click = False

        lbl_text = device_data.get("label_text", self.equip_code)
        self.label = QGraphicsSimpleTextItem(lbl_text, self)
        self.label.setFont(QFont("Segoe UI", 7))
        self.label.setBrush(QBrush(QColor("#2c3e50")))

        self.output_badge = QGraphicsSimpleTextItem("", self)
        self.output_badge.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        self.output_badge.setBrush(QBrush(QColor("#2c3e50")))
        self.output_badge.setVisible(False)

        self._load_icon()
        self._position_label()

        self._glow = QGraphicsDropShadowEffect()
        self._glow.setBlurRadius(15)
        self._glow.setOffset(0, 0)
        self._glow.setColor(self._status_color)
        self._glow.setEnabled(False)
        self.setGraphicsEffect(self._glow)

    def boundingRect(self) -> QRectF:
        return QRectF(
            -self._padding,
            -self._padding,
            self.w + 2 * self._padding,
            self.h + 2 * self._padding,
        )

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_rect = QRectF(0, 0, self.w, self.h)
        corner_radius = 6
        base_color = self._status_color

        path = QPainterPath()
        path.addRoundedRect(bg_rect, corner_radius, corner_radius)

        gradient = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
        if self._is_hovered:
            gradient.setColorAt(0, base_color.lighter(120))
            gradient.setColorAt(1, base_color)
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
        else:
            gradient.setColorAt(0, base_color)
            gradient.setColorAt(1, base_color.darker(110))
            painter.setPen(QPen(base_color.darker(130), 1))

        painter.fillPath(path, QBrush(gradient))
        painter.drawPath(path)

        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)

    def _get_device_base_code(self) -> str:
        """
        Extract base equipment code from device ID.

        Examples:
            "AMX01" -> "AMX"
            "CCT02" -> "CCT"
            "CA111" -> "CA1"
            "CA211" -> "CA2"
        """
        device_id = self.equip_code

        # Special cases for CA1, CA2 (4 character codes)
        if device_id.startswith("CA1") or device_id.startswith("CA2"):
            return device_id[:3]

        # Standard case: first 3 alphabetic characters
        base_code = ""
        for char in device_id:
            if char.isalpha():
                base_code += char
                if len(base_code) >= 3:
                    break

        return base_code.upper() if base_code else device_id[:3].upper()

    def _load_icon(self) -> None:
        """Load icon using ThemeService with caching."""
        target_size = QSize(self.device_data.get("width", 40), self.device_data.get("height", 40))

        pixmap = None

        if self._theme_service:
            # Get base equipment code (e.g., "AMX" from "AMX01")
            base_code = self._get_device_base_code()

            # Use ThemeService for cached, theme-aware device icons
            pixmap = self._theme_service.get_device_pixmap(base_code, target_size)

            if pixmap.isNull():
                logger.warning(f"[DeviceIcon] No icon for {base_code}, using fallback")
                pixmap = self._theme_service.get_pixmap(Icons.LOGO, target_size)
        else:
            # Fallback: direct loading from device_data config (legacy)
            icon_key = "image_dark" if self._is_dark else "image"
            icon_path = self.device_data.get(icon_key, "")

            if not icon_path:
                # Try to construct path from device code
                base_code = self._get_device_base_code()
                suffix = "-white" if self._is_dark else ""
                icon_path = f":/icon/devices/{base_code}{suffix}.svg"

            pm = QPixmap(icon_path)
            if not pm.isNull():
                pixmap = pm.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            else:
                # Final fallback
                pixmap = QPixmap(":/icon/logo.png").scaled(
                    target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )

        if pixmap and not pixmap.isNull():
            if self.w != pixmap.width() or self.h != pixmap.height():
                self.prepareGeometryChange()
                self.w = pixmap.width()
                self.h = pixmap.height()
            self._pixmap = pixmap
            self._position_label()
            if self.output_badge.isVisible():
                br = self.output_badge.boundingRect()
                self.output_badge.setPos(self.w - br.width() + 4, -4)

    def _position_label(self) -> None:
        if not hasattr(self, "label"):
            return

        lbl_rect = self.label.boundingRect()
        spacing = self.device_data.get("label_spacing", 3)
        lbl_pos = self.device_data.get("label_position", "bottom")

        if lbl_pos == "left":
            x = -lbl_rect.width() - spacing
            y = (self.h - lbl_rect.height()) / 2
        elif lbl_pos == "right":
            x = self.w + spacing
            y = (self.h - lbl_rect.height()) / 2
        elif lbl_pos == "top":
            x = (self.w - lbl_rect.width()) / 2
            y = -lbl_rect.height() - spacing
        else:
            x = (self.w - lbl_rect.width()) / 2
            y = self.h + spacing

        self.label.setPos(x, y)

    def update_live_data(self, device_vm: Any) -> None:
        """Update device with live data."""
        status_color_str = "#9E9E9E"
        output_count = 0
        last_update = None
        status_display = "Unknown"

        if isinstance(device_vm, dict):
            status_color_str = device_vm.get("status_color", "#9E9E9E")
            output_count = device_vm.get("output_count", 0) or 0
            last_update = device_vm.get("last_update")
            status_display = device_vm.get("status_name", "Unknown")
        elif hasattr(device_vm, "status_color"):
            status_color_str = device_vm.status_color
            output_count = getattr(device_vm, "output_count", 0) or 0
            last_update = getattr(device_vm, "last_update", None)
            status_display = getattr(device_vm, "status_name", "Unknown")

        new_color = QColor(status_color_str)
        self._status_color = new_color
        self._glow.setColor(new_color)
        self.update()

        if output_count > 0:
            txt = str(output_count)
            if self.output_badge.text() != txt:
                self.output_badge.setText(txt)
                br = self.output_badge.boundingRect()
                self.output_badge.setPos(self.w - br.width() + 4, -4)
                self.output_badge.setVisible(True)
        else:
            self.output_badge.setVisible(False)

        tooltip_text = f"ID: {self.equip_code}\nStatus: {status_display}"
        if last_update:
            clean_time = str(last_update).replace("T", " ").split(".")[0]
            tooltip_text += f"\nUpdated: {clean_time}"
        self.setToolTip(tooltip_text)

    def update_theme(self, is_dark: bool) -> None:
        """Handle theme change - reload icon from cache."""
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            self._load_icon()  # ThemeService handles theming automatically
            c = QColor("#E0E0E0") if is_dark else QColor("#2c3e50")
            self.label.setBrush(QBrush(c))
            self.output_badge.setBrush(QBrush(c))
            self.update()

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self._glow.setEnabled(True)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self._glow.setEnabled(False)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press - start click detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pending_single_click = True

            if self._click_timer is None:
                self._click_timer = QTimer()
                self._click_timer.setSingleShot(True)
                self._click_timer.timeout.connect(self._emit_single_click)

            self._click_timer.start(300)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double click - open right panel."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pending_single_click = False
            if self._click_timer:
                self._click_timer.stop()

            self._parent_canvas.device_double_clicked.emit(self.equip_code)
            logger.debug(f"[DeviceIcon] Double clicked: {self.equip_code}")
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _emit_single_click(self) -> None:
        """Emit single click signal after timer expires."""
        if self._pending_single_click:
            self._pending_single_click = False
            self._parent_canvas.device_clicked.emit(self.equip_code)
            logger.debug(f"[DeviceIcon] Single clicked: {self.equip_code}")


class DeviceCanvasWidget(QWidget):
    """
    Canvas widget displaying factory floor with device icons.

    Uses ThemeService for:
    - Background image theming
    - Device icon theming with caching
    """

    device_clicked = Signal(str)
    device_double_clicked = Signal(str)

    def __init__(
        self,
        area_key: str,
        layout_config: Dict[str, Any],
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.area_key = area_key
        self._layout_config = layout_config
        self._theme_service = theme_service

        self._is_dark = theme_service.is_dark if theme_service else False
        self._device_items: Dict[str, DeviceIconItem] = {}
        self._bg_item = None
        self._ref_width = 1200
        self._ref_height = 600

        self._setup_ui()
        self._init_scene_items()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName(f"canvas_view_{self.area_key}")
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)

        layout.addWidget(self.view)

    def _init_scene_items(self) -> None:
        try:
            if not self._layout_config:
                logger.warning("No layout config provided for %s", self.area_key)
                return

            self._ref_width = self._layout_config.get("ref_width", 1200)
            self._ref_height = self._layout_config.get("ref_height", 600)
            self.scene.setSceneRect(0, 0, self._ref_width, self._ref_height)

            # Load background image
            bg_path = self._get_background_path(self._is_dark)
            bg_pixmap = self._load_background_pixmap(bg_path)

            if bg_pixmap and not bg_pixmap.isNull():
                self._bg_item = self.scene.addPixmap(bg_pixmap)
                self._bg_item.setZValue(-10)
                self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                self._bg_item.setAcceptHoverEvents(False)

            # Create device icons with ThemeService
            for dev in self._layout_config.get("devices", []):
                item = DeviceIconItem(
                    dev,
                    self._ref_width,
                    self._ref_height,
                    self,
                    self._theme_service,  # Pass ThemeService
                )
                self.scene.addItem(item)
                self._device_items[dev["id"]] = item
                logger.debug(f"[Canvas] Added device: {dev['id']}")

            logger.info(f"[Canvas] Initialized {len(self._device_items)} devices for {self.area_key}")

        except Exception as e:
            logger.error("Failed to init canvas items: %s", e)

    def _get_background_path(self, is_dark: bool) -> str:
        """Get background image path using ThemeService."""
        key = self.area_key.lower()

        if "dashboard" in key or "daboard" in key:
            icon = Icons.DASHBOARD_LAYOUT
        else:
            icon = Icons.ORDERS_LAYOUT

        if self._theme_service:
            return self._theme_service.get_icon_path(icon)
        else:
            # Fallback without ThemeService
            return icon.value.dark_path if is_dark else icon.value.light_path

    def _load_background_pixmap(self, path: str) -> Optional[QPixmap]:
        """Load and scale background pixmap."""
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap.scaled(
                self._ref_width,
                self._ref_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        logger.warning(f"[Canvas] Failed to load background: {path}")
        return None

    def render_state(self, devices_state: Dict[str, Any], is_dark: bool) -> None:
        """Render device states with proper color updates."""
        # Update theme if changed
        if is_dark != self._is_dark:
            self._is_dark = is_dark

            # Update background
            if self._bg_item:
                bg_path = self._get_background_path(is_dark)
                pixmap = self._load_background_pixmap(bg_path)
                if pixmap:
                    self._bg_item.setPixmap(pixmap)

            # Update all device icons
            for item in self._device_items.values():
                item.update_theme(is_dark)

        # Update each device's live data
        for dev_id, vm in devices_state.items():
            item = self._device_items.get(dev_id)
            if item:
                item.update_live_data(vm)

        # Force scene update
        self.scene.update()
        self.view.viewport().update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)


__all__ = ["DeviceCanvasWidget", "DeviceIconItem"]
