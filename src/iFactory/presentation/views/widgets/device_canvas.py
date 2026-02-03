"""
Device Canvas - Factory floor visualization.

OPTIMIZATIONS:
1. ColorRegistry for cached colors
2. Removed per-item QGraphicsDropShadowEffect (memory intensive)
3. Hover effect drawn directly in paint instead of effect
4. Cached pixmaps and fonts
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt, Signal, QTimer, QSize
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
)

from ...constants.colors import get_color_registry
from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class DeviceIconItem(QGraphicsObject):
    """
    Individual device icon on the canvas.

    OPTIMIZATIONS:
    - Uses ColorRegistry for cached colors
    - No QGraphicsDropShadowEffect (draws glow manually when hovered)
    - Cached pixmaps via ThemeService
    """

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
        self._colors = get_color_registry()
        self._ref_width = ref_width
        self._ref_height = ref_height

        self._config_width = device_data.get("width", 40)
        self._config_height = device_data.get("height", 40)
        self._display_width: int = self._config_width
        self._display_height: int = self._config_height
        self._padding = 2

        self._status_code: int = 0
        self._is_hovered = False
        self._pixmap: Optional[QPixmap] = None
        self._is_dark = False

        self._click_timer: Optional[QTimer] = None
        self._pending_single_click = False

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        lbl_text = device_data.get("label_text", self.equip_code)
        self.label = QGraphicsSimpleTextItem(lbl_text, self)
        label_font = self._colors.get_font("Segoe UI", 7)
        self.label.setFont(label_font)
        self.label.setBrush(self._colors.get_brush("#2c3e50"))

        self.output_badge = QGraphicsSimpleTextItem("", self)
        badge_font = self._colors.get_font("Segoe UI", 6, QFont.Weight.Bold)
        self.output_badge.setFont(badge_font)
        self.output_badge.setBrush(self._colors.get_brush("#2c3e50"))
        self.output_badge.setVisible(False)

        self._load_icon()

        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height
        self.setPos(x, y)

        self._position_label()

    def boundingRect(self) -> QRectF:
        extra = 4 if self._is_hovered else 0
        return QRectF(
            -self._padding - extra,
            -self._padding - extra,
            self._display_width + 2 * self._padding + 2 * extra,
            self._display_height + 2 * self._padding + 2 * extra,
        )

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_rect = QRectF(0, 0, self._display_width, self._display_height)
        corner_radius = 4

        status_color = self._colors.get_status_color(self._status_code)

        path = QPainterPath()
        path.addRoundedRect(bg_rect, corner_radius, corner_radius)

        if self._is_hovered:
            glow_rect = bg_rect.adjusted(-3, -3, 3, 3)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, corner_radius + 2, corner_radius + 2)

            glow_color = QColor(status_color)
            glow_color.setAlpha(100)
            painter.fillPath(glow_path, glow_color)

        gradient = QLinearGradient(bg_rect.topLeft(), bg_rect.bottomRight())
        if self._is_hovered:
            gradient.setColorAt(0, status_color.lighter(120))
            gradient.setColorAt(1, status_color)
            painter.setPen(QPen(self._colors.get_color("#ffffff"), 1.5))
        else:
            gradient.setColorAt(0, status_color)
            gradient.setColorAt(1, status_color.darker(110))
            painter.setPen(QPen(status_color.darker(130), 1))

        painter.fillPath(path, QBrush(gradient))
        painter.drawPath(path)

        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)

    def _get_device_base_code(self) -> str:
        device_id = self.equip_code

        if device_id.startswith("CA1") or device_id.startswith("CA2"):
            return device_id[:3]

        base_code = ""
        for char in device_id:
            if char.isalpha():
                base_code += char
                if len(base_code) >= 3:
                    break

        return base_code.upper() if base_code else device_id[:3].upper()

    def _load_icon(self) -> None:
        target_size = QSize(self._config_width, self._config_height)
        pixmap: Optional[QPixmap] = None

        if self._theme_service:
            base_code = self._get_device_base_code()
            pixmap = self._theme_service.get_device_pixmap(base_code, target_size)

            if pixmap.isNull():
                logger.warning(f"[DeviceIcon] No icon for {base_code}, using fallback")
                pixmap = self._theme_service.get_pixmap(Icons.LOGO, target_size)
        else:
            icon_key = "image_dark" if self._is_dark else "image"
            icon_path = self.device_data.get(icon_key, "")

            if not icon_path:
                base_code = self._get_device_base_code()
                suffix = "-white" if self._is_dark else ""
                icon_path = f":/icon/devices/{base_code}{suffix}.svg"

            pm = QPixmap(icon_path)
            if not pm.isNull():
                pixmap = pm.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                pixmap = QPixmap(":/icon/logo.png").scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        if pixmap and not pixmap.isNull():
            new_width = pixmap.width()
            new_height = pixmap.height()

            if self._display_width != new_width or self._display_height != new_height:
                self.prepareGeometryChange()
                self._display_width = new_width
                self._display_height = new_height

            self._pixmap = pixmap

            if hasattr(self, "label"):
                self._position_label()
            if hasattr(self, "output_badge") and self.output_badge.isVisible():
                self._position_output_badge()

    def _position_label(self) -> None:
        if not hasattr(self, "label"):
            return

        lbl_rect = self.label.boundingRect()
        spacing = self.device_data.get("label_spacing", 3)
        lbl_pos = self.device_data.get("label_position", "bottom")

        w = self._display_width
        h = self._display_height

        if lbl_pos == "left":
            x = -lbl_rect.width() - spacing
            y = (h - lbl_rect.height()) / 2
        elif lbl_pos == "right":
            x = w + spacing
            y = (h - lbl_rect.height()) / 2
        elif lbl_pos == "top":
            x = (w - lbl_rect.width()) / 2
            y = -lbl_rect.height() - spacing
        else:
            x = (w - lbl_rect.width()) / 2
            y = h + spacing

        self.label.setPos(x, y)

    def _position_output_badge(self) -> None:
        if not hasattr(self, "output_badge"):
            return
        br = self.output_badge.boundingRect()
        self.output_badge.setPos(self._display_width - br.width() + 4, -4)

    def update_live_data(self, device_vm: Any) -> None:
        status_code = 0
        output_count = 0
        last_update = None
        status_display = "Unknown"

        if isinstance(device_vm, dict):
            status_code = device_vm.get("status_code", 0)
            output_count = device_vm.get("output_count", 0) or 0
            last_update = device_vm.get("last_update")
            status_display = device_vm.get("status_name", "Unknown")
        elif hasattr(device_vm, "status_code"):
            status_code = device_vm.status_code
            output_count = getattr(device_vm, "output_count", 0) or 0
            last_update = getattr(device_vm, "last_update", None)
            status_display = getattr(device_vm, "status_name", "Unknown")

        if isinstance(status_code, str):
            try:
                status_code = int(status_code)
            except ValueError:
                status_code = 0

        self._status_code = status_code
        self.update()

        if output_count > 0:
            txt = str(output_count)
            if self.output_badge.text() != txt:
                self.output_badge.setText(txt)
                self.output_badge.setVisible(True)
                self._position_output_badge()
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

            text_color = "#E0E0E0" if is_dark else "#2c3e50"
            text_brush = self._colors.get_brush(text_color)
            self.label.setBrush(text_brush)
            self.output_badge.setBrush(text_brush)
            self.update()

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self.prepareGeometryChange()
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self.prepareGeometryChange()
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
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
        if self._pending_single_click:
            self._pending_single_click = False
            self._parent_canvas.device_clicked.emit(self.equip_code)
            logger.debug(f"[DeviceIcon] Single clicked: {self.equip_code}")


class DeviceCanvasWidget(QWidget):
    """
    Canvas widget displaying factory floor with device icons.

    OPTIMIZATIONS:
    - Uses ColorRegistry for all colors
    - ThemeService for cached pixmaps
    - No per-item effects
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
        self._colors = get_color_registry()

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
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        layout.addWidget(self.view)

    def _init_scene_items(self) -> None:
        try:
            if not self._layout_config:
                logger.warning("No layout config provided for %s", self.area_key)
                return

            self._ref_width = self._layout_config.get("ref_width", 1200)
            self._ref_height = self._layout_config.get("ref_height", 600)
            self.scene.setSceneRect(0, 0, self._ref_width, self._ref_height)

            bg_path = self._get_background_path(self._is_dark)
            bg_pixmap = self._load_background_pixmap(bg_path)

            if bg_pixmap and not bg_pixmap.isNull():
                self._bg_item = self.scene.addPixmap(bg_pixmap)
                self._bg_item.setZValue(-10)
                self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                self._bg_item.setAcceptHoverEvents(False)

            for dev in self._layout_config.get("devices", []):
                item = DeviceIconItem(
                    dev,
                    self._ref_width,
                    self._ref_height,
                    self,
                    self._theme_service,
                )
                self.scene.addItem(item)
                self._device_items[dev["id"]] = item

            logger.info(f"[Canvas] Initialized {len(self._device_items)} devices for {self.area_key}")

        except Exception as e:
            logger.error("Failed to init canvas items: %s", e)

    def _get_background_path(self, is_dark: bool) -> str:
        key = self.area_key.lower()

        if "dashboard" in key or "daboard" in key:
            icon = Icons.DASHBOARD_LAYOUT
        else:
            icon = Icons.ORDERS_LAYOUT

        if self._theme_service:
            return self._theme_service.get_icon_path(icon)
        else:
            return icon.value.dark_path if is_dark else icon.value.light_path

    def _load_background_pixmap(self, path: str) -> Optional[QPixmap]:
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
        if is_dark != self._is_dark:
            self._is_dark = is_dark

            if self._bg_item:
                bg_path = self._get_background_path(is_dark)
                pixmap = self._load_background_pixmap(bg_path)
                if pixmap:
                    self._bg_item.setPixmap(pixmap)

            for item in self._device_items.values():
                item.update_theme(is_dark)

        for dev_id, vm in devices_state.items():
            item = self._device_items.get(dev_id)
            if item:
                item.update_live_data(vm)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)


__all__ = ["DeviceCanvasWidget", "DeviceIconItem"]
