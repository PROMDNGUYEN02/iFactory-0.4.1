"""
Device Canvas Widget - Khắc phục lỗi Scale Tab Ẩn và Font chuẩn.
"""

import json
import logging
from pathlib import Path
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsTextItem, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QColor, QFont, QPainter
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)


class DeviceIconItem(QGraphicsPixmapItem):
    def __init__(self, device_data, ref_width, ref_height, parent_canvas):
        super().__init__()
        self.device_data = device_data
        self.equip_code = device_data["id"]
        self._parent_canvas = parent_canvas

        self.w = device_data.get("width", 40)
        self.h = device_data.get("height", 40)
        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height

        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)

        lbl_text = device_data.get("label_text", self.equip_code)
        lbl_pos = device_data.get("label_position", "left")

        self.label = QGraphicsTextItem(lbl_text, self)
        # --- FIX #4: GIẢM FONT XUỐNG 11px ĐỂ NHÌN GỌN GÀNG HƠN ---
        self.label.setFont(QFont("Arial", 11, QFont.Bold))

        lbl_rect = self.label.boundingRect()
        spacing = device_data.get("label_spacing", 2)
        if lbl_pos == "left":
            self.label.setPos(-lbl_rect.width() - spacing, (self.h - lbl_rect.height()) / 2)
        elif lbl_pos == "top":
            self.label.setPos((self.w - lbl_rect.width()) / 2, -lbl_rect.height() - spacing)
        elif lbl_pos == "bottom":
            self.label.setPos((self.w - lbl_rect.width()) / 2, self.h + spacing)

        self.update_theme(False)

    def update_theme(self, is_dark: bool):
        icon_path = self.device_data["image_dark"] if is_dark else self.device_data["image"]
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            pixmap = QPixmap(":/icon/logo.png")
        self.setPixmap(pixmap.scaled(self.w, self.h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        text_color = QColor("white") if is_dark else QColor("black")
        self.label.setDefaultTextColor(text_color)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._parent_canvas.device_clicked.emit(self.equip_code)
            event.accept()
        super().mousePressEvent(event)


class DeviceCanvasWidget(QWidget):
    device_clicked = Signal(str)

    def __init__(self, area_key: str, parent=None):
        super().__init__(parent)
        self.area_key = area_key
        self._is_dark = False

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.layout.addWidget(self.view)
        self._device_items = {}
        self._bg_item = None
        self._ref_width = 1200
        self._ref_height = 600

        self._load_positions()

    def _load_positions(self):
        try:
            pos_file = Path("data/device_positions.json")
            if pos_file.exists():
                with open(pos_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    area_data = data.get(self.area_key, {})

                    self._ref_width = area_data.get("ref_width", 1200)
                    self._ref_height = area_data.get("ref_height", 600)
                    self.scene.setSceneRect(0, 0, self._ref_width, self._ref_height)

                    bg_img = ":/icon/dashboard_layout.svg" if "daboard" in self.area_key else ":/icon/orders_layout.svg"
                    bg_pixmap = QPixmap(bg_img).scaled(self._ref_width, self._ref_height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    self._bg_item = self.scene.addPixmap(bg_pixmap)
                    self._bg_item.setZValue(-1)

                    devices = area_data.get("devices", [])
                    for dev in devices:
                        item = DeviceIconItem(dev, self._ref_width, self._ref_height, self)
                        self.scene.addItem(item)
                        self._device_items[dev["id"]] = item
        except Exception as e:
            logger.error(f"Failed to load canvas positions: {e}")

    def render_state(self, view_models: dict, is_dark: bool):
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            bg_img = (
                (":/icon/dashboard_layout-white.svg" if "daboard" in self.area_key else ":/icon/orders_layout-white.svg")
                if is_dark
                else (":/icon/dashboard_layout.svg" if "daboard" in self.area_key else ":/icon/orders_layout.svg")
            )
            if self._bg_item:
                self._bg_item.setPixmap(QPixmap(bg_img).scaled(self._ref_width, self._ref_height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            for item in self._device_items.values():
                item.update_theme(is_dark)

    # --- FIX #3: LỖI KHÔNG SCALE CỦA TRANG ORDER ---
    # Sự kiện này chỉ chạy khi Tab thực sự được bấm vào và hiện lên màn hình
    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)


__all__ = ["DeviceCanvasWidget"]
