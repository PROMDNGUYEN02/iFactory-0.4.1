"""
Device Canvas Widget - Factory Map Visualization.
Renders device icons with status-based BACKGROUND FILL color.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from iFactory.infrastructure.configuration.paths import PATHS

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
    QBrush,
    QPen,
    QLinearGradient,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
    QWidget,
    QStyleOptionGraphicsItem,
)

logger = logging.getLogger(__name__)


class DeviceIconItem(QGraphicsObject):
    """Interactive device icon with status-based BACKGROUND FILL."""

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
        self._padding = 4

        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height
        self.setPos(x, y)

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self._status_color = QColor(Qt.transparent)  # Default transparent
        self._is_hovered = False

        self._pixmap: Optional[QPixmap] = None
        self._is_dark = False
        self._load_icon()

        lbl_text = device_data.get("label_text", self.equip_code)
        self.label = QGraphicsTextItem(lbl_text, self)
        self.label.setFont(QFont("Segoe UI", 7))
        self._position_label()

        self.output_badge = QGraphicsTextItem("", self)
        self.output_badge.setFont(QFont("Segoe UI", 6, QFont.Bold))
        self.output_badge.setVisible(False)

        self._glow = QGraphicsDropShadowEffect()
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
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

        bg_rect = QRectF(
            -self._padding,
            -self._padding,
            self.w + 2 * self._padding,
            self.h + 2 * self._padding,
        )
        corner_radius = 6

        gradient = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
        base_color = QColor(self._status_color)

        if self._is_hovered:
            gradient.setColorAt(0, base_color.lighter(120))
            gradient.setColorAt(1, base_color)
        else:
            gradient.setColorAt(0, base_color)
            gradient.setColorAt(1, base_color.darker(110))

        path = QPainterPath()
        path.addRoundedRect(bg_rect, corner_radius, corner_radius)
        painter.fillPath(path, QBrush(gradient))

        border_color = base_color.darker(130) if not self._is_hovered else QColor("#ffffff")
        painter.setPen(QPen(border_color, 1.5 if self._is_hovered else 1))
        painter.drawPath(path)

        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)

    def _load_icon(self) -> None:
        icon_key = "image_dark" if self._is_dark else "image"
        icon_path = self.device_data.get(icon_key, "")

        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self._pixmap = pixmap.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                return

        self._pixmap = QPixmap(":/icon/logo.png").scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _position_label(self) -> None:
        lbl_rect = self.label.boundingRect()
        spacing = self.device_data.get("label_spacing", 3)
        lbl_pos = self.device_data.get("label_position", "bottom")

        if lbl_pos == "left":
            self.label.setPos(-lbl_rect.width() - spacing - self._padding, (self.h - lbl_rect.height()) / 2)
        elif lbl_pos == "right":
            self.label.setPos(self.w + spacing + self._padding, (self.h - lbl_rect.height()) / 2)
        elif lbl_pos == "top":
            self.label.setPos((self.w - lbl_rect.width()) / 2, -lbl_rect.height() - spacing - self._padding)
        else:
            self.label.setPos((self.w - lbl_rect.width()) / 2, self.h + spacing + self._padding)

    def update_live_data(self, device_vm) -> None:
        """Update from ViewModel - handles DeviceViewModel, dict, or any object with status_color."""
        status_color = None
        output_count = 0
        last_update = None
        status_display = "Unknown"

        # 1. Extract Data (bao gồm cả last_update và status_display)
        if hasattr(device_vm, "status_color"):
            status_color = device_vm.status_color
            output_count = getattr(device_vm, "output_count", 0) or 0
            last_update = getattr(device_vm, "last_update", None)
            status_display = getattr(device_vm, "status_display", "Unknown")
        elif isinstance(device_vm, dict):
            status_color = device_vm.get("status_color", "#9E9E9E")
            output_count = device_vm.get("output_count", 0) or 0
            last_update = device_vm.get("last_update")
            status_display = device_vm.get("status_display", "Unknown")

        # 2. Update Visuals (Color)
        if status_color:
            new_color = QColor(status_color)
            if new_color.isValid() and new_color != self._status_color:
                self._status_color = new_color
                self._glow.setColor(new_color)
                self.update()

        # 3. Update Badge
        if output_count > 0:
            self.output_badge.setPlainText(str(output_count))
            self.output_badge.setPos(self.w - 8, -self._padding - 8)
            self.output_badge.setVisible(True)
        else:
            self.output_badge.setVisible(False)

        # 4. Update Tooltip
        tooltip_text = f"ID: {self.equip_code}\nStatus: {status_display}"
        if last_update:
            clean_time = str(last_update).replace("T", " ").split(".")[0]
            tooltip_text += f"\nUpdated: {clean_time}"

        self.setToolTip(tooltip_text)

    def update_theme(self, is_dark: bool) -> None:
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            self._load_icon()
            text_color = QColor("#E0E0E0") if is_dark else QColor("#2c3e50")
            self.label.setDefaultTextColor(text_color)
            self.output_badge.setDefaultTextColor(text_color)
            self.update()

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self._glow.setBlurRadius(15)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self._glow.setBlurRadius(0)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._parent_canvas.device_clicked.emit(self.equip_code)
            event.accept()
        super().mousePressEvent(event)


class DeviceCanvasWidget(QWidget):
    """Canvas displaying factory device map with filled backgrounds."""

    device_clicked = Signal(str)

    def __init__(self, area_key: str, parent=None):
        super().__init__(parent)
        self.area_key = area_key
        self._is_dark = False
        self._device_items: Dict[str, DeviceIconItem] = {}
        self._bg_item = None
        self._ref_width = 1200
        self._ref_height = 600

        self._setup_ui()
        self._load_positions()

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
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        layout.addWidget(self.view)

    def _load_positions(self) -> None:
        try:
            pos_file = PATHS.device_positions_path
            if not pos_file.exists():
                logger.warning(f"Device positions file not found: {pos_file}")
                return

            data = json.loads(pos_file.read_text(encoding="utf-8"))
            area_data = data.get(self.area_key, {})

            self._ref_width = area_data.get("ref_width", 1200)
            self._ref_height = area_data.get("ref_height", 600)
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

            for dev in area_data.get("devices", []):
                item = DeviceIconItem(dev, self._ref_width, self._ref_height, self)
                self.scene.addItem(item)
                self._device_items[dev["id"]] = item

        except Exception as e:
            logger.error(f"Failed to load canvas positions: {e}")

    def _get_background_image(self, is_dark: bool) -> str:
        suffix = "-white.svg" if is_dark else ".svg"
        if "daboard" in self.area_key.lower() or "dashboard" in self.area_key.lower():
            base = "dashboard_layout"
        else:
            base = "orders_layout"
        return f":/icon/{base}{suffix}"

    def render_state(self, devices_state: Dict[str, Any], is_dark: bool) -> None:
        """Render devices from ViewModels."""
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

        for dev_id, vm in devices_state.items():
            if dev_id in self._device_items:
                self._device_items[dev_id].update_live_data(vm)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)


__all__ = ["DeviceCanvasWidget"]
