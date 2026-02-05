# File: src/iFactory/presentation/views/widgets/device_canvas.py
"""
Device Canvas - Factory floor visualization.

FEATURES:
- Full-frame background (stretches to fill entire view)
- Device icons scale with background
- Synchronized scaling on resize
- Hover tooltips with rich content
- Selection state with visual feedback
- Click/double-click handling
- Theme support (light/dark)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    QSizeF,
    QTimer,
    Property,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ...constants.colors import get_color_registry
from ..components.base import AnimationDuration

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


# ============================================================================
# Device Icon Item
# ============================================================================
class DeviceIconItem(QGraphicsObject):
    """
    Device icon with animations and interactions.

    Features:
    - Smooth status color transitions
    - Pulse animation for alerts
    - Selection state
    - Rich tooltips
    - Glow effect on hover
    - Synchronized scaling with canvas
    """

    _glow_radius: float = 0.0
    _pulse_scale: float = 1.0

    def __init__(
        self,
        device_data: Dict[str, Any],
        parent_canvas: "DeviceCanvasWidget",
        theme_service: Optional["ThemeService"] = None,
    ):
        super().__init__()
        self.device_data = device_data
        self.equip_code = device_data["id"]
        self._parent_canvas = parent_canvas
        self._theme_service = theme_service
        self._colors = get_color_registry()

        # Store percentage positions (0-100)
        self._x_percent = device_data.get("x_percent", 0)
        self._y_percent = device_data.get("y_percent", 0)

        # Original config dimensions
        self._config_width = device_data.get("width", 40)
        self._config_height = device_data.get("height", 40)

        # Current display dimensions (scaled)
        self._display_width: float = self._config_width
        self._display_height: float = self._config_height
        self._padding = 2

        # Current scale factors
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0

        self._status_code: int = 0
        self._previous_status_code: int = 0
        self._is_hovered = False
        self._is_selected = False
        self._is_alerting = False
        self._pixmap: Optional[QPixmap] = None
        self._original_pixmap: Optional[QPixmap] = None
        self._is_dark = False

        # Animation state
        self._glow_radius = 0.0
        self._pulse_scale = 1.0
        self._current_color = QColor("#888888")
        self._target_color = QColor("#888888")

        # Animation references
        self._active_animations: List[QPropertyAnimation] = []

        # Timers
        self._click_timer: Optional[QTimer] = None
        self._pending_single_click = False
        self._pulse_timer: Optional[QTimer] = None
        self._pulse_direction = 1

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # Label
        lbl_text = device_data.get("label_text", self.equip_code)
        self.label = QGraphicsSimpleTextItem(lbl_text, self)
        label_font = self._colors.get_font("Segoe UI", 7)
        self.label.setFont(label_font)
        self.label.setBrush(self._colors.get_brush("#2c3e50"))

        # Output badge
        self.output_badge = QGraphicsSimpleTextItem("", self)
        badge_font = self._colors.get_font("Segoe UI", 6, QFont.Weight.Bold)
        self.output_badge.setFont(badge_font)
        self.output_badge.setBrush(self._colors.get_brush("#2c3e50"))
        self.output_badge.setVisible(False)

        self._load_icon()
        self._position_label()

    # ========================================================================
    # Animation Properties
    # ========================================================================

    def get_glow_radius(self) -> float:
        return self._glow_radius

    def set_glow_radius(self, value: float) -> None:
        self._glow_radius = value
        self.update()

    glow_radius = Property(float, get_glow_radius, set_glow_radius)

    def get_pulse_scale(self) -> float:
        return self._pulse_scale

    def set_pulse_scale(self, value: float) -> None:
        self._pulse_scale = value
        self.prepareGeometryChange()
        self.update()

    pulse_scale = Property(float, get_pulse_scale, set_pulse_scale)

    # ========================================================================
    # Rendering
    # ========================================================================

    def boundingRect(self) -> QRectF:
        extra = max(10, self._glow_radius) if self._is_hovered or self._is_alerting else 4
        scale_extra = (self._pulse_scale - 1.0) * self._display_width / 2
        total_extra = extra + scale_extra

        return QRectF(
            -self._padding - total_extra,
            -self._padding - total_extra,
            self._display_width + 2 * self._padding + 2 * total_extra,
            self._display_height + 2 * self._padding + 2 * total_extra,
        )

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply pulse scale
        if self._pulse_scale != 1.0:
            center_x = self._display_width / 2
            center_y = self._display_height / 2
            painter.translate(center_x, center_y)
            painter.scale(self._pulse_scale, self._pulse_scale)
            painter.translate(-center_x, -center_y)

        bg_rect = QRectF(0, 0, self._display_width, self._display_height)
        corner_radius = 4 * min(self._scale_x, self._scale_y)  # Scale corner radius

        status_color = self._colors.get_status_color(self._status_code)

        path = QPainterPath()
        path.addRoundedRect(bg_rect, corner_radius, corner_radius)

        # Glow effect
        if self._glow_radius > 0:
            glow_rect = bg_rect.adjusted(-self._glow_radius, -self._glow_radius, self._glow_radius, self._glow_radius)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, corner_radius + self._glow_radius / 2, corner_radius + self._glow_radius / 2)

            glow_color = QColor(status_color)
            alpha = int(150 * (self._glow_radius / 10))
            glow_color.setAlpha(min(alpha, 150))
            painter.fillPath(glow_path, glow_color)

        # Selection indicator
        if self._is_selected:
            select_rect = bg_rect.adjusted(-3, -3, 3, 3)
            select_path = QPainterPath()
            select_path.addRoundedRect(select_rect, corner_radius + 2, corner_radius + 2)
            painter.setPen(QPen(self._colors.get_color("#3B82F6"), 2))
            painter.drawPath(select_path)

        # Background gradient
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

        # Icon
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)

    # ========================================================================
    # Status Updates
    # ========================================================================

    def update_live_data(self, device_vm: Any) -> None:
        """Update with animated status transition."""
        if isinstance(device_vm, dict):
            status_code = device_vm.get("status_code", 0)
            output_count = device_vm.get("output_count", 0) or 0
            last_update = device_vm.get("last_update")
            status_display = device_vm.get("status_name", "Unknown")
        else:
            status_code = getattr(device_vm, "status_code", 0)
            output_count = getattr(device_vm, "output_count", 0) or 0
            last_update = getattr(device_vm, "last_update", None)
            status_display = getattr(device_vm, "status_name", "Unknown")

        if isinstance(status_code, str):
            try:
                status_code = int(status_code)
            except ValueError:
                status_code = 0

        # Animate status change
        if status_code != self._status_code:
            self._previous_status_code = self._status_code
            self._status_code = status_code
            self._animate_status_change()

            if status_code in (2, 3):
                self._start_pulse_animation()
            else:
                self._stop_pulse_animation()

        self.update()

        # Output badge
        if output_count > 0:
            txt = str(output_count)
            if self.output_badge.text() != txt:
                self.output_badge.setText(txt)
                self.output_badge.setVisible(True)
                self._position_output_badge()
        else:
            self.output_badge.setVisible(False)

        # Tooltip
        tooltip_text = self._build_tooltip(status_display, output_count, last_update)
        self.setToolTip(tooltip_text)

    def _build_tooltip(self, status: str, output: int, last_update: Any) -> str:
        """Build rich tooltip content."""
        lines = [
            f"<b>{self.equip_code}</b>",
            f"<hr>",
            f"Status: <span style='color: {self._get_status_color_hex()}'>{status}</span>",
        ]

        if output > 0:
            lines.append(f"Output: {output}")

        if last_update:
            clean_time = str(last_update).replace("T", " ").split(".")[0]
            lines.append(f"Updated: {clean_time}")

        return "<br>".join(lines)

    def _get_status_color_hex(self) -> str:
        """Get current status color as hex."""
        color = self._colors.get_status_color(self._status_code)
        return color.name()

    def _animate_status_change(self) -> None:
        """Animate color transition on status change."""
        self._cleanup_animations()

        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setKeyValueAt(0, 0)
        anim.setKeyValueAt(0.5, 8)
        anim.setKeyValueAt(1, 0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._remove_animation(anim))
        self._active_animations.append(anim)
        anim.start()

    def _cleanup_animations(self) -> None:
        """Clean up finished animations."""
        self._active_animations = [a for a in self._active_animations if a.state() == QPropertyAnimation.State.Running]

    def _remove_animation(self, anim: QPropertyAnimation) -> None:
        """Remove animation from tracking list."""
        if anim in self._active_animations:
            self._active_animations.remove(anim)

    def _start_pulse_animation(self) -> None:
        """Start continuous pulse for alerts."""
        if self._is_alerting:
            return

        self._is_alerting = True

        if not self._pulse_timer:
            self._pulse_timer = QTimer()
            self._pulse_timer.timeout.connect(self._pulse_step)

        self._pulse_direction = 1
        self._pulse_timer.start(50)

    def _stop_pulse_animation(self) -> None:
        """Stop pulse animation."""
        self._is_alerting = False

        if self._pulse_timer:
            self._pulse_timer.stop()

        self._pulse_scale = 1.0
        self.update()

    def _pulse_step(self) -> None:
        """Pulse animation step."""
        step = 0.005

        if self._pulse_direction > 0:
            self._pulse_scale += step
            if self._pulse_scale >= 1.05:
                self._pulse_direction = -1
        else:
            self._pulse_scale -= step
            if self._pulse_scale <= 1.0:
                self._pulse_direction = 1

        self.prepareGeometryChange()
        self.update()

    # ========================================================================
    # Selection
    # ========================================================================

    def set_selected(self, selected: bool) -> None:
        """Set selection state with animation."""
        if selected == self._is_selected:
            return

        self._is_selected = selected
        self._cleanup_animations()

        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(self._glow_radius)
        anim.setEndValue(6 if selected else 0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._remove_animation(anim))
        self._active_animations.append(anim)
        anim.start()

    # ========================================================================
    # Icon Loading
    # ========================================================================

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
        """Load original icon (unscaled)."""
        target_size = QSize(self._config_width, self._config_height)
        pixmap: Optional[QPixmap] = None

        if self._theme_service:
            base_code = self._get_device_base_code()
            pixmap = self._theme_service.get_device_pixmap(base_code, target_size)

            if pixmap.isNull():
                logger.warning(f"[DeviceIcon] No icon for {base_code}, using fallback")
                try:
                    from ...resources.icons import Icons

                    pixmap = self._theme_service.get_pixmap(Icons.LOGO, target_size)
                except (ImportError, AttributeError):
                    pixmap = QPixmap(":/icon/logo.png").scaled(
                        target_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
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
            self._original_pixmap = pixmap
            self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        """Update pixmap to current scale."""
        if not self._original_pixmap or self._original_pixmap.isNull():
            return

        # Calculate scaled size
        scaled_width = int(self._config_width * self._scale_x)
        scaled_height = int(self._config_height * self._scale_y)

        if scaled_width <= 0 or scaled_height <= 0:
            return

        self._pixmap = self._original_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # Update display dimensions
        self._display_width = self._pixmap.width()
        self._display_height = self._pixmap.height()

    def _position_label(self) -> None:
        if not hasattr(self, "label"):
            return

        # Scale font size
        base_font_size = 7
        scaled_font_size = max(6, int(base_font_size * min(self._scale_x, self._scale_y)))
        label_font = self._colors.get_font("Segoe UI", scaled_font_size)
        self.label.setFont(label_font)

        lbl_rect = self.label.boundingRect()
        spacing = self.device_data.get("label_spacing", 3) * min(self._scale_x, self._scale_y)
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
        else:  # bottom
            x = (w - lbl_rect.width()) / 2
            y = h + spacing

        self.label.setPos(x, y)

    def _position_output_badge(self) -> None:
        if not hasattr(self, "output_badge"):
            return

        # Scale font size
        base_font_size = 6
        scaled_font_size = max(5, int(base_font_size * min(self._scale_x, self._scale_y)))
        badge_font = self._colors.get_font("Segoe UI", scaled_font_size, QFont.Weight.Bold)
        self.output_badge.setFont(badge_font)

        br = self.output_badge.boundingRect()
        self.output_badge.setPos(self._display_width - br.width() + 4, -4)

    # ========================================================================
    # Theme
    # ========================================================================

    def update_theme(self, is_dark: bool) -> None:
        if is_dark == self._is_dark:
            return

        self._is_dark = is_dark
        self._load_icon()
        self._update_scaled_pixmap()

        text_color = "#E0E0E0" if is_dark else "#2c3e50"
        text_brush = self._colors.get_brush(text_color)
        self.label.setBrush(text_brush)
        self.output_badge.setBrush(text_brush)

    # ========================================================================
    # Transform & Position Updates
    # ========================================================================

    def update_transform(self, scene_width: float, scene_height: float, scale_x: float, scale_y: float) -> None:
        """
        Update position and size based on new scene dimensions and scale factors.

        Args:
            scene_width: Current scene width
            scene_height: Current scene height
            scale_x: Horizontal scale factor
            scale_y: Vertical scale factor
        """
        self.prepareGeometryChange()

        # Store scale factors
        self._scale_x = scale_x
        self._scale_y = scale_y

        # Update position based on percentage
        x = (self._x_percent / 100) * scene_width
        y = (self._y_percent / 100) * scene_height
        self.setPos(x, y)

        # Update scaled pixmap and dimensions
        self._update_scaled_pixmap()

        # Reposition label and badge
        self._position_label()
        if self.output_badge.isVisible():
            self._position_output_badge()

        self.update()

    # ========================================================================
    # Mouse Events
    # ========================================================================

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True
        self._cleanup_animations()

        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(0)
        anim.setEndValue(8)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._remove_animation(anim))
        self._active_animations.append(anim)
        anim.start()

        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False
        self._cleanup_animations()

        target = 6 if self._is_selected else 0
        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(self._glow_radius)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._remove_animation(anim))
        self._active_animations.append(anim)
        anim.start()

        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pending_single_click = True

            if self._click_timer is None:
                self._click_timer = QTimer()
                self._click_timer.setSingleShot(True)
                self._click_timer.timeout.connect(self._emit_single_click)

            self._click_timer.start(250)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pending_single_click = False
            if self._click_timer:
                self._click_timer.stop()

            self._parent_canvas.device_double_clicked.emit(self.equip_code)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _emit_single_click(self) -> None:
        if self._pending_single_click:
            self._pending_single_click = False
            self._parent_canvas.device_clicked.emit(self.equip_code)


# ============================================================================
# Device Canvas Widget - Full Frame Background
# ============================================================================
class DeviceCanvasWidget(QWidget):
    """
    Canvas widget with full-frame background.

    Features:
    - Background stretches to fill entire view (full width AND height)
    - Device icons scale proportionally with background
    - Synchronized positioning - devices never drift from background
    - Smooth resize handling
    - Theme support
    """

    device_clicked = Signal(str)
    device_double_clicked = Signal(str)
    selection_changed = Signal(list)

    def __init__(
        self,
        area_key: str,
        layout_config: Dict[str, Any],
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.area_key = area_key
        self._layout_config = layout_config or {}
        self._theme_service = theme_service
        self._colors = get_color_registry()

        self._is_dark = theme_service.is_dark if theme_service else False
        self._device_items: Dict[str, DeviceIconItem] = {}
        self._selected_devices: Set[str] = set()
        self._bg_item: Optional[QGraphicsPixmapItem] = None

        # Original reference dimensions from config (design space)
        self._config_ref_width = self._layout_config.get("ref_width", 1200)
        self._config_ref_height = self._layout_config.get("ref_height", 600)

        # Current display dimensions (updated on resize)
        self._display_width: float = self._config_ref_width
        self._display_height: float = self._config_ref_height

        # Scale factors
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0

        # Original background pixmap (unscaled)
        self._original_bg_pixmap: Optional[QPixmap] = None

        # Resize debounce timer
        self._resize_timer: Optional[QTimer] = None

        self._setup_ui()
        self._load_original_background()
        self._init_scene_items()

    def _setup_ui(self) -> None:
        """Setup UI - full frame canvas."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scene and View
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName(f"canvas_view_{self.area_key}")
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setInteractive(True)

        # Disable scroll wheel zoom
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Make view expand to fill available space
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self.view)

        # Resize debounce timer
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(16)  # ~60fps
        self._resize_timer.timeout.connect(self._do_resize)

    def _load_original_background(self) -> None:
        """Load original background pixmap (unscaled)."""
        try:
            bg_path = self._get_background_path(self._is_dark)
            if bg_path:
                self._original_bg_pixmap = QPixmap(bg_path)
                if self._original_bg_pixmap.isNull():
                    logger.warning(f"[Canvas] Failed to load background: {bg_path}")
                    self._original_bg_pixmap = None
                else:
                    logger.debug(f"[Canvas] Background loaded: {bg_path}")
                    # Update config ref dimensions from actual image if not set
                    if self._layout_config.get("ref_width") is None:
                        self._config_ref_width = self._original_bg_pixmap.width()
                    if self._layout_config.get("ref_height") is None:
                        self._config_ref_height = self._original_bg_pixmap.height()
        except Exception as e:
            logger.warning(f"[Canvas] Background load failed: {e}")
            self._original_bg_pixmap = None

    def _init_scene_items(self) -> None:
        """Initialize scene with devices from config."""
        try:
            if not self._layout_config:
                logger.warning(f"[Canvas] No layout config provided for {self.area_key}")
                return

            # Initial scene rect
            self.scene.setSceneRect(0, 0, self._display_width, self._display_height)

            # Add background item
            self._update_background()

            # Load devices
            devices = self._layout_config.get("devices", [])
            if not devices:
                logger.warning(f"[Canvas] No devices in config for {self.area_key}")
            else:
                for dev in devices:
                    try:
                        item = DeviceIconItem(
                            dev,
                            self,
                            self._theme_service,
                        )
                        self.scene.addItem(item)
                        self._device_items[dev["id"]] = item
                    except Exception as dev_error:
                        logger.warning(f"[Canvas] Failed to create device {dev.get('id', '?')}: {dev_error}")

                logger.info(f"[Canvas] Initialized {len(self._device_items)} devices for {self.area_key}")

        except Exception as e:
            logger.error(f"[Canvas] Failed to init canvas for {self.area_key}: {e}")

    def _get_background_path(self, is_dark: bool) -> Optional[str]:
        """Get background image path based on area and theme."""
        key = self.area_key.lower()

        try:
            from ...resources.icons import Icons

            if "electrode" in key:
                icon = Icons.ELECTRODE_LAYOUT
            elif "assembly" in key:
                icon = Icons.ASSEMBLY_LAYOUT
            else:
                return None

            if self._theme_service:
                return self._theme_service.get_icon_path(icon)
            else:
                return icon.value.dark_path if is_dark else icon.value.light_path

        except (ImportError, AttributeError) as e:
            logger.debug(f"[Canvas] Layout icon enum not available: {e}")

            suffix = "-white" if is_dark else ""
            if "electrode" in key:
                return f":/icon/electrode_layout{suffix}.svg"
            elif "assembly" in key:
                return f":/icon/assembly_layout{suffix}.svg"

            return None

    def _update_background(self) -> None:
        """Update background to fill current display size (stretched)."""
        if not self._original_bg_pixmap or self._original_bg_pixmap.isNull():
            return

        # Stretch background to fill entire display area
        scaled_pixmap = self._original_bg_pixmap.scaled(
            int(self._display_width),
            int(self._display_height),
            Qt.AspectRatioMode.IgnoreAspectRatio,  # Stretch to fill completely
            Qt.TransformationMode.SmoothTransformation,
        )

        if self._bg_item:
            self._bg_item.setPixmap(scaled_pixmap)
        else:
            self._bg_item = self.scene.addPixmap(scaled_pixmap)
            self._bg_item.setZValue(-10)
            self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            self._bg_item.setAcceptHoverEvents(False)

    def _update_device_transforms(self) -> None:
        """Update all device positions and sizes based on current scale."""
        for item in self._device_items.values():
            item.update_transform(
                self._display_width,
                self._display_height,
                self._scale_x,
                self._scale_y,
            )

    def _fit_to_view(self) -> None:
        """Fit content to view - stretches to fill entire viewport."""
        view_width = self.view.viewport().width()
        view_height = self.view.viewport().height()

        if view_width <= 0 or view_height <= 0:
            return

        # Update display dimensions to match view
        self._display_width = float(view_width)
        self._display_height = float(view_height)

        # Calculate scale factors relative to config reference
        self._scale_x = self._display_width / self._config_ref_width
        self._scale_y = self._display_height / self._config_ref_height

        # Update scene rect to match view
        self.scene.setSceneRect(0, 0, self._display_width, self._display_height)

        # Update background (stretched to fill)
        self._update_background()

        # Update device positions and sizes
        self._update_device_transforms()

        # Reset view transform - scene already matches view size
        self.view.resetTransform()

    def _do_resize(self) -> None:
        """Perform the actual resize (debounced)."""
        self._fit_to_view()

    # ========================================================================
    # Selection
    # ========================================================================

    def select_device(self, device_id: str, multi_select: bool = False) -> None:
        """Select a device."""
        if not multi_select:
            for dev_id in self._selected_devices:
                if dev_id in self._device_items:
                    self._device_items[dev_id].set_selected(False)
            self._selected_devices.clear()

        if device_id in self._device_items:
            if device_id in self._selected_devices:
                self._selected_devices.remove(device_id)
                self._device_items[device_id].set_selected(False)
            else:
                self._selected_devices.add(device_id)
                self._device_items[device_id].set_selected(True)

        self.selection_changed.emit(list(self._selected_devices))

    def clear_selection(self) -> None:
        """Clear all selections."""
        for dev_id in self._selected_devices:
            if dev_id in self._device_items:
                self._device_items[dev_id].set_selected(False)
        self._selected_devices.clear()
        self.selection_changed.emit([])

    # ========================================================================
    # Rendering
    # ========================================================================

    def render_state(self, devices_state: Dict[str, Any], is_dark: bool) -> None:
        """Render devices with theme handling."""
        theme_changed = is_dark != self._is_dark

        if theme_changed:
            self._is_dark = is_dark
            self._update_theme(is_dark)

        for dev_id, vm in devices_state.items():
            item = self._device_items.get(dev_id)
            if item:
                item.update_live_data(vm)

    def _update_theme(self, is_dark: bool) -> None:
        """Update theme for all elements."""
        # Reload original background for new theme
        self._load_original_background()
        self._update_background()

        # Update devices
        self.scene.blockSignals(True)
        try:
            for item in self._device_items.values():
                item.update_theme(is_dark)
        finally:
            self.scene.blockSignals(False)

        self.scene.update()

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit to view when shown
        QTimer.singleShot(0, self._fit_to_view)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Debounce resize for performance
        if self._resize_timer:
            self._resize_timer.start()

    # ========================================================================
    # Public API
    # ========================================================================

    def get_device_item(self, device_id: str) -> Optional[DeviceIconItem]:
        """Get device item by ID."""
        return self._device_items.get(device_id)

    def get_all_device_ids(self) -> List[str]:
        """Get all device IDs."""
        return list(self._device_items.keys())

    def center_on_device(self, device_id: str) -> None:
        """Center view on a specific device."""
        item = self._device_items.get(device_id)
        if item:
            self.view.centerOn(item)

    def get_scale_factors(self) -> tuple[float, float]:
        """Get current scale factors (x, y)."""
        return (self._scale_x, self._scale_y)

    def get_display_size(self) -> tuple[float, float]:
        """Get current display size (width, height)."""
        return (self._display_width, self._display_height)


__all__ = ["DeviceCanvasWidget", "DeviceIconItem"]
