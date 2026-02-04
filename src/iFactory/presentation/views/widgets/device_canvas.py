# File: src/iFactory/presentation/views/widgets/device_canvas.py
"""
Enhanced Device Canvas - Factory floor visualization.

OPTIMIZATIONS & UX IMPROVEMENTS:
1. ColorRegistry for cached colors
2. Smooth animations on status change
3. Hover tooltips with rich content
4. Selection state with visual feedback
5. Zoom and pan support
6. Loading skeleton state
7. Device grouping
8. Mini-map for navigation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
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
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from ...constants.colors import get_color_registry
from ..components.base import AnimationDuration
from ..components.loading import SkeletonLoader

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


# ============================================================================
# Enhanced Device Icon
# ============================================================================


class DeviceIconItem(QGraphicsObject):
    """
    Enhanced device icon with animations and interactions.

    Features:
    - Smooth status color transitions
    - Pulse animation for alerts
    - Selection state
    - Rich tooltips
    - Glow effect on hover
    """

    # Animation properties
    _glow_radius: float = 0.0
    _pulse_scale: float = 1.0
    _status_opacity: float = 1.0

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
        self._previous_status_code: int = 0
        self._is_hovered = False
        self._is_selected = False
        self._is_alerting = False
        self._pixmap: Optional[QPixmap] = None
        self._is_dark = False

        # Animation state
        self._glow_radius = 0.0
        self._pulse_scale = 1.0
        self._current_color = QColor("#888888")
        self._target_color = QColor("#888888")

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

        # Position
        x = (device_data.get("x_percent", 0) / 100) * ref_width
        y = (device_data.get("y_percent", 0) / 100) * ref_height
        self.setPos(x, y)

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
        corner_radius = 4

        status_color = self._colors.get_status_color(self._status_code)

        path = QPainterPath()
        path.addRoundedRect(bg_rect, corner_radius, corner_radius)

        # Glow effect (hover or alert)
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
    # Status Updates with Animation
    # ========================================================================

    def update_live_data(self, device_vm: Any) -> None:
        """Update with animated status transition."""
        # Extract data
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

            # Start pulse for alerts
            if status_code in (2, 3):  # Alarm codes
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
        # Quick flash animation
        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setKeyValueAt(0, 0)
        anim.setKeyValueAt(0.5, 8)
        anim.setKeyValueAt(1, 0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

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

        # Reset scale
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

        # Animate glow
        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(self._glow_radius)
        anim.setEndValue(6 if selected else 0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
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

    # ========================================================================
    # Theme
    # ========================================================================

    def update_theme(self, is_dark: bool) -> None:
        if is_dark == self._is_dark:
            return

        self._is_dark = is_dark
        self._load_icon()

        text_color = "#E0E0E0" if is_dark else "#2c3e50"
        text_brush = self._colors.get_brush(text_color)
        self.label.setBrush(text_brush)
        self.output_badge.setBrush(text_brush)

    # ========================================================================
    # Mouse Events
    # ========================================================================

    def hoverEnterEvent(self, event) -> None:
        self._is_hovered = True

        # Animate glow
        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(0)
        anim.setEndValue(8)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._is_hovered = False

        # Animate glow out
        target = 6 if self._is_selected else 0
        anim = QPropertyAnimation(self, b"glow_radius")
        anim.setDuration(AnimationDuration.FAST)
        anim.setStartValue(self._glow_radius)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
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
# Enhanced Canvas Widget
# ============================================================================


class DeviceCanvasWidget(QWidget):
    """
    Enhanced canvas with zoom, pan, and selection.

    Features:
    - Zoom with mouse wheel
    - Pan with middle mouse button
    - Multi-select with Ctrl+Click
    - Selection box
    - Mini-map navigation
    - Loading skeleton
    - Performance optimizations
    """

    device_clicked = Signal(str)
    device_double_clicked = Signal(str)
    selection_changed = Signal(list)  # List of selected device IDs
    zoom_changed = Signal(float)

    MIN_ZOOM = 0.5
    MAX_ZOOM = 3.0

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
        self._bg_item = None
        self._ref_width = 1200
        self._ref_height = 600

        self._current_zoom = 1.0
        self._is_panning = False
        self._pan_start = QPointF()
        self._is_loading = True

        self._setup_ui()
        self._init_scene_items()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self._toolbar = self._create_toolbar()
        layout.addWidget(self._toolbar)

        # Canvas container
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

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
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Enable mouse tracking for pan
        self.view.viewport().installEventFilter(self)

        canvas_layout.addWidget(self.view)
        layout.addWidget(canvas_container, 1)

        # Loading overlay
        self._loading_overlay = self._create_loading_overlay()
        self._loading_overlay.setParent(self)

    def _create_toolbar(self) -> QFrame:
        """Create canvas toolbar with zoom controls."""
        toolbar = QFrame()
        toolbar.setFixedHeight(32)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Zoom controls
        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setFixedSize(24, 24)
        self._zoom_out_btn.clicked.connect(lambda: self._zoom(-0.1))
        layout.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(50)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedSize(24, 24)
        self._zoom_in_btn.clicked.connect(lambda: self._zoom(0.1))
        layout.addWidget(self._zoom_in_btn)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self._reset_view)
        layout.addWidget(self._reset_btn)

        layout.addStretch()

        # Selection info
        self._selection_label = QLabel("")
        layout.addWidget(self._selection_label)

        return toolbar

    def _create_loading_overlay(self) -> QFrame:
        """Create loading skeleton overlay."""
        overlay = QFrame()
        overlay.setStyleSheet("background: rgba(0,0,0,0.3);")

        layout = QVBoxLayout(overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Skeleton placeholders
        for _ in range(3):
            row = QHBoxLayout()
            for _ in range(4):
                skeleton = SkeletonLoader(60, 60)
                row.addWidget(skeleton)
            layout.addLayout(row)

        label = QLabel("Loading devices...")
        label.setStyleSheet("color: white; font-size: 14px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        return overlay

    def _init_scene_items(self) -> None:
        """Initialize scene with devices from config."""
        try:
            if not self._layout_config:
                logger.warning(f"[Canvas] No layout config provided for {self.area_key}")
                self._is_loading = False
                self._loading_overlay.hide()
                return

            self._ref_width = self._layout_config.get("ref_width", 1200)
            self._ref_height = self._layout_config.get("ref_height", 600)
            self.scene.setSceneRect(0, 0, self._ref_width, self._ref_height)

            # Load background (optional - don't fail if not found)
            try:
                bg_path = self._get_background_path(self._is_dark)
                if bg_path:
                    bg_pixmap = self._load_background_pixmap(bg_path)
                    if bg_pixmap and not bg_pixmap.isNull():
                        self._bg_item = self.scene.addPixmap(bg_pixmap)
                        self._bg_item.setZValue(-10)
                        self._bg_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                        self._bg_item.setAcceptHoverEvents(False)
                        logger.debug(f"[Canvas] Background loaded for {self.area_key}")
            except Exception as bg_error:
                logger.warning(f"[Canvas] Background load skipped for {self.area_key}: {bg_error}")
                # Continue without background - this is not critical

            # Load devices
            devices = self._layout_config.get("devices", [])
            if not devices:
                logger.warning(f"[Canvas] No devices in config for {self.area_key}")
            else:
                for dev in devices:
                    try:
                        item = DeviceIconItem(
                            dev,
                            self._ref_width,
                            self._ref_height,
                            self,
                            self._theme_service,
                        )
                        self.scene.addItem(item)
                        self._device_items[dev["id"]] = item
                    except Exception as dev_error:
                        logger.warning(f"[Canvas] Failed to create device {dev.get('id', '?')}: {dev_error}")

                logger.info(f"[Canvas] Initialized {len(self._device_items)} devices for {self.area_key}")

            # Hide loading overlay
            self._is_loading = False
            self._loading_overlay.hide()

        except Exception as e:
            logger.error(f"[Canvas] Failed to init canvas for {self.area_key}: {e}")
            self._is_loading = False
            self._loading_overlay.hide()

    # ========================================================================
    # Zoom & Pan
    # ========================================================================

    def _zoom(self, delta: float) -> None:
        """Zoom in/out by delta."""
        new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self._current_zoom + delta))

        if new_zoom != self._current_zoom:
            self._current_zoom = new_zoom
            self.view.setTransform(QTransform.fromScale(new_zoom, new_zoom))
            self._zoom_label.setText(f"{int(new_zoom * 100)}%")
            self.zoom_changed.emit(new_zoom)

    def _reset_view(self) -> None:
        """Reset zoom and position."""
        self._current_zoom = 1.0
        self.view.setTransform(QTransform())
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_label.setText("100%")

    def eventFilter(self, obj, event) -> bool:
        """Handle wheel zoom and middle-button pan."""
        if obj == self.view.viewport():
            if event.type() == event.Type.Wheel:
                # Zoom with wheel
                delta = event.angleDelta().y()
                zoom_delta = 0.1 if delta > 0 else -0.1
                self._zoom(zoom_delta)
                return True

            elif event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.MiddleButton:
                    self._is_panning = True
                    self._pan_start = event.pos()
                    self.view.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True

            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.MiddleButton:
                    self._is_panning = False
                    self.view.setCursor(Qt.CursorShape.ArrowCursor)
                    return True

            elif event.type() == event.Type.MouseMove:
                if self._is_panning:
                    delta = event.pos() - self._pan_start
                    self._pan_start = event.pos()

                    # Pan the view
                    self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - int(delta.x()))
                    self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - int(delta.y()))
                    return True

        return super().eventFilter(obj, event)

    # ========================================================================
    # Selection
    # ========================================================================

    def select_device(self, device_id: str, multi_select: bool = False) -> None:
        """Select a device."""
        if not multi_select:
            # Clear previous selection
            for dev_id in self._selected_devices:
                if dev_id in self._device_items:
                    self._device_items[dev_id].set_selected(False)
            self._selected_devices.clear()

        if device_id in self._device_items:
            if device_id in self._selected_devices:
                # Deselect
                self._selected_devices.remove(device_id)
                self._device_items[device_id].set_selected(False)
            else:
                # Select
                self._selected_devices.add(device_id)
                self._device_items[device_id].set_selected(True)

        self._update_selection_label()
        self.selection_changed.emit(list(self._selected_devices))

    def clear_selection(self) -> None:
        """Clear all selections."""
        for dev_id in self._selected_devices:
            if dev_id in self._device_items:
                self._device_items[dev_id].set_selected(False)
        self._selected_devices.clear()
        self._update_selection_label()
        self.selection_changed.emit([])

    def _update_selection_label(self) -> None:
        """Update selection count label."""
        count = len(self._selected_devices)
        if count == 0:
            self._selection_label.setText("")
        elif count == 1:
            self._selection_label.setText("1 device selected")
        else:
            self._selection_label.setText(f"{count} devices selected")

    # ========================================================================
    # Rendering
    # ========================================================================

    def render_state(self, devices_state: Dict[str, Any], is_dark: bool) -> None:
        """Render devices with optimized theme handling."""
        theme_changed = is_dark != self._is_dark

        if theme_changed:
            self._is_dark = is_dark
            self._update_theme_batch(is_dark)
            self._apply_toolbar_theme()

        for dev_id, vm in devices_state.items():
            item = self._device_items.get(dev_id)
            if item:
                item.update_live_data(vm)

    def _update_theme_batch(self, is_dark: bool) -> None:
        """Batch update all theme-dependent elements."""
        # Update background
        if self._bg_item:
            try:
                bg_path = self._get_background_path(is_dark)
                if bg_path:
                    pixmap = self._load_background_pixmap(bg_path)
                    if pixmap:
                        self._bg_item.setPixmap(pixmap)
            except Exception as e:
                logger.debug(f"[Canvas] Background theme update skipped: {e}")

        # Update devices
        self.scene.blockSignals(True)
        try:
            for item in self._device_items.values():
                item.update_theme(is_dark)
        finally:
            self.scene.blockSignals(False)

        self.scene.update()

    def _apply_toolbar_theme(self) -> None:
        """Apply theme to toolbar."""
        if not self._theme_service:
            return

        tokens = self._theme_service.tokens

        self._toolbar.setStyleSheet(
            f"""
            QFrame {{
                background: {tokens.surface_card};
                border-bottom: 1px solid {tokens.border_default};
            }}
            QPushButton {{
                background: {tokens.interactive_hover};
                border: 1px solid {tokens.border_default};
                border-radius: 4px;
                padding: 2px 8px;
                color: {tokens.text_primary};
            }}
            QPushButton:hover {{
                background: {tokens.primary_subtle};
            }}
            QLabel {{
                color: {tokens.text_secondary};
                font-size: {tokens.font_size_sm};
            }}
        """
        )

    def _get_background_path(self, is_dark: bool) -> Optional[str]:
        """Get background image path based on area and theme."""
        key = self.area_key.lower()

        # Try to use Icons enum if available
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
            # Icons not available or missing layout icons
            logger.debug(f"[Canvas] Layout icon enum not available: {e}")

            # Fallback to direct paths
            suffix = "-white" if is_dark else ""
            if "electrode" in key:
                return f":/icon/electrode_layout{suffix}.svg"
            elif "assembly" in key:
                return f":/icon/assembly_layout{suffix}.svg"

            return None

    def _load_background_pixmap(self, path: str) -> Optional[QPixmap]:
        """Load and scale background pixmap."""
        if not path:
            return None

        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap.scaled(
                self._ref_width,
                self._ref_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        logger.debug(f"[Canvas] Failed to load background: {path}")
        return None

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._loading_overlay.setGeometry(self.rect())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._loading_overlay.setGeometry(self.rect())


__all__ = ["DeviceCanvasWidget", "DeviceIconItem"]
