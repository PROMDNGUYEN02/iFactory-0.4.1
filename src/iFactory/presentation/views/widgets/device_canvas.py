# File: presentation/views/widgets/device_canvas.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QRectF, Qt, Signal, QTimer
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

logger = logging.getLogger(__name__)


class DeviceIconItem(QGraphicsObject):
    def __init__(
        self,
        device_data: Dict[str, Any],
        ref_width: int,
        ref_height: int,
        parent_canvas: "DeviceCanvasWidget",
    ):
        super().__init__()
        self.device_data = device_data
        self.equip_code = device_data["id"]
        self._parent_canvas = parent_canvas

        self.w = device_data.get("width", 40)
        self.h = device_data.get("height", 40)
        self._padding = 2

        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height
        self.setPos(x, y)

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        self._status_color = QColor("#9E9E9E")  # Default gray
        self._is_hovered = False
        self._pixmap: Optional[QPixmap] = None
        self._is_dark = False
        self._click_count = 0
        self._double_click_timer: Optional[QTimer] = None

        lbl_text = device_data.get("label_text", self.equip_code)
        self.label = QGraphicsSimpleTextItem(lbl_text, self)
        self.label.setFont(QFont("Segoe UI", 7))
        self.label.setBrush(QBrush(QColor("#2c3e50")))

        self.output_badge = QGraphicsSimpleTextItem("", self)
        self.output_badge.setFont(QFont("Segoe UI", 6, QFont.Bold))
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
        painter.setRenderHint(QPainter.Antialiasing)

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

    def _load_icon(self) -> None:
        icon_key = "image_dark" if self._is_dark else "image"
        icon_path = self.device_data.get(icon_key, "")
        if not icon_path:
            icon_path = ":/icon/logo.png"

        pm = QPixmap(icon_path)
        if not pm.isNull():
            target_w = self.device_data.get("width", 40)
            target_h = self.device_data.get("height", 40)

            scaled_pm = pm.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            if self.w != scaled_pm.width() or self.h != scaled_pm.height():
                self.prepareGeometryChange()
                self.w = scaled_pm.width()
                self.h = scaled_pm.height()
                self._pixmap = scaled_pm
                self._position_label()
                if self.output_badge.isVisible():
                    br = self.output_badge.boundingRect()
                    self.output_badge.setPos(self.w - br.width() + 4, -4)
            else:
                self._pixmap = scaled_pm

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

        # Always update color
        new_color = QColor(status_color_str)
        self._status_color = new_color
        self._glow.setColor(new_color)

        # Force repaint
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
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            self._load_icon()
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
        """Handle mouse press - detect single vs double click."""
        if event.button() == Qt.LeftButton:
            self._click_count += 1

            if self._click_count == 1:
                if self._double_click_timer is None:
                    self._double_click_timer = QTimer()
                    self._double_click_timer.setSingleShot(True)
                    self._double_click_timer.timeout.connect(self._on_single_click_confirmed)

                self._double_click_timer.start(250)

            event.accept()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double click - open right panel."""
        if event.button() == Qt.LeftButton:
            self._click_count = 0
            if self._double_click_timer:
                self._double_click_timer.stop()

            self._parent_canvas.device_double_clicked.emit(self.equip_code)
            logger.debug(f"[DeviceIcon] Double clicked: {self.equip_code}")
            event.accept()
        super().mouseDoubleClickEvent(event)

    def _on_single_click_confirmed(self) -> None:
        """Called when single click is confirmed."""
        if self._click_count == 1:
            self._parent_canvas.device_clicked.emit(self.equip_code)
            logger.debug(f"[DeviceIcon] Single clicked: {self.equip_code}")
        self._click_count = 0


class DeviceCanvasWidget(QWidget):
    device_clicked = Signal(str)
    device_double_clicked = Signal(str)

    def __init__(
        self,
        area_key: str,
        layout_config: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.area_key = area_key
        self._layout_config = layout_config

        self._is_dark = False
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
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # Force full update
        self.view.setCacheMode(QGraphicsView.CacheNone)  # Disable cache for live updates

        layout.addWidget(self.view)

    def _init_scene_items(self) -> None:
        try:
            if not self._layout_config:
                logger.warning("No layout config provided for %s", self.area_key)
                return

            self._ref_width = self._layout_config.get("ref_width", 1200)
            self._ref_height = self._layout_config.get("ref_height", 600)
            self.scene.setSceneRect(0, 0, self._ref_width, self._ref_height)

            bg_img = self._get_background_image(False)
            bg_pixmap = QPixmap(bg_img)
            if not bg_pixmap.isNull():
                bg_pixmap = bg_pixmap.scaled(
                    self._ref_width,
                    self._ref_height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
                self._bg_item = self.scene.addPixmap(bg_pixmap)
                self._bg_item.setZValue(-10)
                self._bg_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                self._bg_item.setAcceptHoverEvents(False)

            for dev in self._layout_config.get("devices", []):
                item = DeviceIconItem(dev, self._ref_width, self._ref_height, self)
                self.scene.addItem(item)
                self._device_items[dev["id"]] = item
                logger.debug(f"[Canvas] Added device: {dev['id']}")

        except Exception as e:
            logger.error("Failed to init canvas items: %s", e)

    def _get_background_image(self, is_dark: bool) -> str:
        suffix = "-white.svg" if is_dark else ".svg"
        key = self.area_key.lower()
        base = "dashboard_layout" if ("dashboard" in key or "daboard" in key) else "orders_layout"
        return f":/icon/{base}{suffix}"

    def render_state(self, devices_state: Dict[str, Any], is_dark: bool) -> None:
        """Render device states with proper color updates."""
        logger.debug(f"[Canvas] render_state called with {len(devices_state)} devices, is_dark={is_dark}")

        # Update theme if changed
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            if self._bg_item:
                bg_img = self._get_background_image(is_dark)
                pixmap = QPixmap(bg_img)
                if not pixmap.isNull():
                    self._bg_item.setPixmap(
                        pixmap.scaled(
                            self._ref_width,
                            self._ref_height,
                            Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    )
            for item in self._device_items.values():
                item.update_theme(is_dark)

        # Update each device's live data
        for dev_id, vm in devices_state.items():
            item = self._device_items.get(dev_id)
            if item:
                item.update_live_data(vm)
                logger.debug(f"[Canvas] Updated device {dev_id}")

        # Force scene update
        self.scene.update()
        self.view.viewport().update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)


__all__ = ["DeviceCanvasWidget"]
