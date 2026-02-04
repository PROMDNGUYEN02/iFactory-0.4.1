# src/iFactory/presentation/views/widgets/gantt_canvas.py
"""
Enhanced Gantt Canvas Widget - Optimized with UX improvements.

Key Features:
1. Viewport culling - only draw visible segments
2. Smooth animations on data updates
3. Interactive segments with hover details
4. Time ruler with current time indicator
5. Responsive resize handling
6. Loading skeleton state
7. Export functionality

Fixed:
- QGradient::setColorAt position validation (must be in range 0-1)
- Segment clipping to prevent negative positions
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...constants.colors import get_color_registry, ColorRegistry
from ...constants.status import Status
from ..components.base import AnimationDuration, SkeletonLoader

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels.models.gantt_model import (
        GanttSegmentModel,
        GanttChartModel,
        GanttStatsModel,
    )

logger = logging.getLogger(__name__)

STATUS_GRADIENTS = ColorRegistry.STATUS_GRADIENTS


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to the specified range."""
    return max(min_val, min(max_val, value))


class PrecomputedSegment:
    """Pre-computed segment geometry for fast rendering."""

    __slots__ = (
        "x",
        "width",
        "status_code",
        "status_name",
        "start_time",
        "end_time",
        "duration_seconds",
        "is_visible",
        "hover_opacity",
    )

    def __init__(
        self,
        x: float,
        width: float,
        status_code: int,
        status_name: str,
        start_time: datetime,
        end_time: datetime,
        duration_seconds: float,
    ):
        self.x = x
        self.width = width
        self.status_code = status_code
        self.status_name = status_name
        self.start_time = start_time
        self.end_time = end_time
        self.duration_seconds = duration_seconds
        self.is_visible = True
        self.hover_opacity = 1.0


class GanttCanvasWidget(QWidget):
    """
    Enhanced compact stacked bar chart for multiple devices.

    Features:
    - Viewport culling for performance
    - Smooth animations
    - Interactive hover
    - Time ruler with now indicator
    - Loading state
    """

    device_clicked = Signal(str)
    segment_hovered = Signal(str, object)  # device_id, segment

    LABEL_WIDTH = 70
    RULER_HEIGHT = 18
    BAR_HEIGHT = 10
    BAR_SPACING = 3
    MAX_DEVICES = 8

    def __init__(
        self,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
        is_compact: bool = False,
    ):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._colors = get_color_registry()

        self._precomputed_data: Dict[str, List[PrecomputedSegment]] = {}
        self._device_order: List[str] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._total_seconds: float = 0
        self._is_compact = is_compact

        self._cached_chart_width: float = 0
        self._cached_bar_height: float = self.BAR_HEIGHT

        self._hovered_device: Optional[str] = None
        self._hovered_segment_index: int = -1
        self._is_loading = True

        # Animation
        self._fade_opacity = 0.0
        self._animation: Optional[QPropertyAnimation] = None

        self.setMinimumHeight(60)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._theme_service.themeChanged.connect(self._on_theme_changed)

        # Now indicator timer
        self._now_timer = QTimer(self)
        self._now_timer.timeout.connect(self.update)
        self._now_timer.start(60000)  # Update every minute

    # ========================================================================
    # Animation Properties
    # ========================================================================

    def get_fade_opacity(self) -> float:
        return self._fade_opacity

    def set_fade_opacity(self, value: float) -> None:
        self._fade_opacity = value
        self.update()

    fade_opacity = Property(float, get_fade_opacity, set_fade_opacity)

    # ========================================================================
    # Theme
    # ========================================================================

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self.update()

    @property
    def tokens(self):
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        return self._theme_service.is_dark

    # ========================================================================
    # Data Rendering
    # ========================================================================

    def render_timeline(
        self,
        data: Dict[str, List[Any]],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Render timeline with animation."""
        self._precomputed_data.clear()
        self._device_order.clear()

        if not data:
            self._start_time = None
            self._end_time = None
            self._is_loading = False
            self.update()
            return

        if not end:
            end = datetime.now()
        if not start:
            start = end - timedelta(hours=24)

        self._start_time = start
        self._end_time = end
        self._total_seconds = max((end - start).total_seconds(), 1)

        rect = self.rect()
        chart_width = rect.width() - self.LABEL_WIDTH - 10
        if chart_width <= 0:
            chart_width = 400
        self._cached_chart_width = chart_width

        for device_code, segments in list(data.items())[: self.MAX_DEVICES]:
            self._device_order.append(device_code)
            precomputed = self._precompute_segments(segments, chart_width, self._total_seconds)
            self._precomputed_data[device_code] = precomputed

        self._is_loading = False

        # Fade in animation
        self._animate_fade_in()

        logger.debug(f"GanttCanvas: precomputed {len(self._device_order)} devices")

    def _animate_fade_in(self) -> None:
        """Animate chart fade in."""
        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"fade_opacity")
        self._animation.setDuration(AnimationDuration.NORMAL)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def _precompute_segments(
        self,
        segments: List[Any],
        chart_width: float,
        total_seconds: float,
    ) -> List[PrecomputedSegment]:
        """Pre-compute segment geometry with proper clipping."""
        result: List[PrecomputedSegment] = []

        for seg in segments:
            if isinstance(seg, dict):
                seg_start = seg.get("start_time")
                seg_end = seg.get("end_time")
                status_code = seg.get("status_code", 0)
                status_name = seg.get("status_name", "")
            else:
                seg_start = getattr(seg, "start_time", None)
                seg_end = getattr(seg, "end_time", None)
                status_code = getattr(seg, "status_code", 0)
                status_name = getattr(seg, "status_name", "")

            if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
                continue

            # Skip segments completely outside the window
            if seg_end < self._start_time or seg_start > self._end_time:
                continue

            # FIXED: Clip segment to window bounds
            clipped_start = max(seg_start, self._start_time)
            clipped_end = min(seg_end, self._end_time)

            # Calculate offsets from clipped times (always >= 0)
            start_offset = (clipped_start - self._start_time).total_seconds()
            end_offset = (clipped_end - self._start_time).total_seconds()

            if end_offset <= start_offset:
                continue

            # Now x and width are guaranteed to be >= 0
            x = (start_offset / total_seconds) * chart_width
            width = max(((end_offset - start_offset) / total_seconds) * chart_width, 2)
            duration = (clipped_end - clipped_start).total_seconds()

            result.append(
                PrecomputedSegment(
                    x=x,
                    width=width,
                    status_code=int(status_code) if status_code else 0,
                    status_name=status_name or Status.get_name(status_code),
                    start_time=clipped_start,
                    end_time=clipped_end,
                    duration_seconds=duration,
                )
            )

        return result

    # ========================================================================
    # Painting
    # ========================================================================

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self.tokens

        bg_color = self._colors.get_color(tokens.surface_app)
        text_color = self._colors.get_color(tokens.text_muted)
        grid_color = self._colors.get_color(tokens.border_default)
        track_color = self._colors.get_color(tokens.interactive_hover)

        painter.fillRect(rect, bg_color)

        # Loading state
        if self._is_loading:
            self._draw_loading(painter, rect, text_color)
            return

        # Empty state
        if not self._precomputed_data or not self._start_time or not self._end_time:
            self._draw_empty_state(painter, rect, text_color)
            return

        # Apply fade opacity
        if self._fade_opacity < 1.0:
            painter.setOpacity(self._fade_opacity)

        num_devices = len(self._device_order)
        available_height = rect.height() - self.RULER_HEIGHT - 8

        if num_devices > 0 and available_height > 0:
            bar_height = max(
                6,
                min(
                    self.BAR_HEIGHT,
                    (available_height - (num_devices - 1) * self.BAR_SPACING) // num_devices,
                ),
            )
        else:
            bar_height = self.BAR_HEIGHT

        self._cached_bar_height = bar_height
        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10

        if chart_width <= 0:
            return

        visible_rect = QRectF(chart_left, 0, chart_width, rect.height())

        label_font = self._colors.get_font("Consolas", 9)
        painter.setFont(label_font)

        y = 6
        track_brush = QBrush(track_color)
        no_pen = QPen(Qt.PenStyle.NoPen)

        for device_idx, device_code in enumerate(self._device_order):
            if y + bar_height > available_height + 6:
                break

            is_hovered_device = device_code == self._hovered_device

            # Device label
            painter.setPen(text_color)
            label_rect = QRectF(4, y, self.LABEL_WIDTH - 8, bar_height)
            display_label = device_code[:8] if len(device_code) > 8 else device_code

            if is_hovered_device:
                painter.setPen(self._colors.get_color(tokens.text_primary))

            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                display_label,
            )

            # Track background with rounded corners
            bar_rect = QRectF(chart_left, y, chart_width, bar_height)

            track_path = QPainterPath()
            track_path.addRoundedRect(bar_rect, 3, 3)
            painter.setPen(no_pen)
            painter.fillPath(track_path, track_brush)

            # Segments
            segments = self._precomputed_data.get(device_code, [])
            for seg_idx, seg in enumerate(segments):
                seg_x = chart_left + seg.x
                if seg_x + seg.width < visible_rect.left():
                    continue
                if seg_x > visible_rect.right():
                    continue

                is_hovered = is_hovered_device and seg_idx == self._hovered_segment_index

                seg_rect = QRectF(seg_x, y, seg.width, bar_height)

                # Get gradient colors
                start_color, end_color = self._colors.get_status_gradient_colors(seg.status_code)

                if is_hovered:
                    start_color = start_color.lighter(115)
                    end_color = end_color.lighter(110)

                # FIXED: Create gradient with valid positions (0 and 1)
                gradient = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
                gradient.setColorAt(0.0, start_color)
                gradient.setColorAt(1.0, end_color)

                seg_path = QPainterPath()
                seg_path.addRoundedRect(seg_rect, 2, 2)
                painter.fillPath(seg_path, QBrush(gradient))

                # Hover border
                if is_hovered:
                    painter.setPen(QPen(QColor("#FFFFFF"), 1))
                    painter.drawPath(seg_path)

            y += bar_height + self.BAR_SPACING

        # Time ruler
        ruler_y = rect.height() - self.RULER_HEIGHT
        self._draw_ruler(painter, rect, chart_left, chart_width, ruler_y, text_color, grid_color)

        # Now indicator
        self._draw_now_indicator(painter, chart_left, chart_width, 6, ruler_y)

    def _draw_loading(self, painter: QPainter, rect: QRectF, text_color: QColor) -> None:
        """Draw loading state."""
        font = self._colors.get_font(self.tokens.font_family, 10)
        painter.setPen(text_color)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "⏳ Loading timeline...")

    def _draw_empty_state(self, painter: QPainter, rect: QRectF, text_color: QColor) -> None:
        """Draw empty state."""
        font = self._colors.get_font(self.tokens.font_family, 10)
        painter.setPen(text_color)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "📊 No timeline data")

    def _draw_ruler(
        self,
        painter: QPainter,
        rect: QRectF,
        chart_left: float,
        chart_width: float,
        ruler_y: float,
        text_color: QColor,
        grid_color: QColor,
    ) -> None:
        """Draw time ruler with improved styling."""
        if not self._start_time or not self._end_time:
            return

        ruler_font = self._colors.get_font("Consolas", 8)
        painter.setFont(ruler_font)

        # Ruler line
        grid_pen = self._colors.get_pen(self.tokens.border_default, 1)
        painter.setPen(grid_pen)
        painter.drawLine(int(chart_left), int(ruler_y), int(chart_left + chart_width), int(ruler_y))

        current = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current < self._start_time:
            current += timedelta(hours=1)

        total_seconds = self._total_seconds

        while current <= self._end_time:
            offset = (current - self._start_time).total_seconds()
            x = chart_left + (offset / total_seconds) * chart_width

            if x < chart_left or x > chart_left + chart_width:
                current += timedelta(hours=1)
                continue

            # Tick marks
            painter.setPen(grid_pen)
            is_major = current.hour % 6 == 0
            tick_height = 6 if is_major else 3
            painter.drawLine(int(x), int(ruler_y), int(x), int(ruler_y + tick_height))

            # Time labels for major ticks
            if is_major:
                painter.setPen(text_color)
                time_str = current.strftime("%H:%M")
                painter.drawText(
                    int(x) - 20,
                    int(ruler_y + 6),
                    40,
                    12,
                    Qt.AlignmentFlag.AlignCenter,
                    time_str,
                )

            current += timedelta(hours=1)

    def _draw_now_indicator(
        self,
        painter: QPainter,
        chart_left: float,
        chart_width: float,
        top_y: float,
        bottom_y: float,
    ) -> None:
        """Draw current time indicator."""
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return
        if not (self._start_time <= now <= self._end_time):
            return

        total_seconds = self._total_seconds
        now_offset = (now - self._start_time).total_seconds()

        # FIXED: Clamp position to valid range
        position_ratio = clamp(now_offset / total_seconds, 0.0, 1.0)
        x = chart_left + position_ratio * chart_width

        error_color = self._colors.get_color(self.tokens.error)

        # Vertical line
        painter.setPen(QPen(error_color, 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(int(x), int(top_y), int(x), int(bottom_y))

        # Triangle marker
        painter.setBrush(QBrush(error_color))
        painter.setPen(Qt.PenStyle.NoPen)

        marker_path = QPainterPath()
        marker_path.moveTo(x, top_y - 2)
        marker_path.lineTo(x + 5, top_y + 4)
        marker_path.lineTo(x - 5, top_y + 4)
        marker_path.closeSubpath()
        painter.drawPath(marker_path)

        # "Now" label
        painter.setPen(error_color)
        font = self._colors.get_font("Consolas", 7, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(int(x) - 12, int(top_y - 10), "Now")

    # ========================================================================
    # Mouse Events
    # ========================================================================

    def mouseMoveEvent(self, event) -> None:
        if not self._precomputed_data or not self._start_time:
            return

        pos = event.position()
        rect = self.rect()

        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10
        available_height = rect.height() - self.RULER_HEIGHT - 8

        bar_height = self._cached_bar_height

        old_device = self._hovered_device
        old_segment = self._hovered_segment_index

        self._hovered_device = None
        self._hovered_segment_index = -1

        y = 6
        for device_code in self._device_order:
            if y + bar_height > available_height + 6:
                break

            if y <= pos.y() <= y + bar_height and pos.x() >= chart_left:
                self._hovered_device = device_code

                # Find hovered segment
                segments = self._precomputed_data.get(device_code, [])
                for i, seg in enumerate(segments):
                    seg_x = chart_left + seg.x
                    if seg_x <= pos.x() <= seg_x + seg.width:
                        self._hovered_segment_index = i

                        # Show tooltip
                        tooltip = self._build_segment_tooltip(device_code, seg)
                        QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)

                        self.segment_hovered.emit(device_code, seg)
                        break
                break

            y += bar_height + self.BAR_SPACING

        # Repaint if hover changed
        if old_device != self._hovered_device or old_segment != self._hovered_segment_index:
            self.update()

        if self._hovered_segment_index < 0:
            QToolTip.hideText()

    def _build_segment_tooltip(self, device_code: str, seg: PrecomputedSegment) -> str:
        """Build rich tooltip for segment."""
        duration_str = self._format_duration(seg.duration_seconds)
        time_range = f"{seg.start_time.strftime('%H:%M:%S')} - " f"{seg.end_time.strftime('%H:%M:%S')}"

        return f"<b>{device_code}</b><br>" f"<hr>" f"Status: <b>{seg.status_name}</b><br>" f"Duration: {duration_str}<br>" f"Time: {time_range}"

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m = int(seconds) // 60
            s = int(seconds) % 60
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._hovered_device:
            self.device_clicked.emit(self._hovered_device)

    def leaveEvent(self, event) -> None:
        self._hovered_device = None
        self._hovered_segment_index = -1
        self.update()
        QToolTip.hideText()

    # ========================================================================
    # Resize
    # ========================================================================

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._precomputed_data and self._start_time and self._end_time:
            rect = self.rect()
            chart_width = rect.width() - self.LABEL_WIDTH - 10
            if chart_width > 0 and chart_width != self._cached_chart_width:
                self._recompute_geometry(chart_width)

    def _recompute_geometry(self, chart_width: float) -> None:
        """Recompute segment geometry on resize."""
        if not self._total_seconds:
            return

        self._cached_chart_width = chart_width

        for device_code, segments in self._precomputed_data.items():
            for seg in segments:
                # FIXED: Use clipped times (already stored in segment)
                start_offset = (seg.start_time - self._start_time).total_seconds()
                end_offset = (seg.end_time - self._start_time).total_seconds()

                # Ensure non-negative values
                start_offset = max(0, start_offset)
                end_offset = max(start_offset, end_offset)

                seg.x = (start_offset / self._total_seconds) * chart_width
                seg.width = max(((end_offset - start_offset) / self._total_seconds) * chart_width, 2)


# ============================================================================
# Progress Bar Widget (Enhanced)
# ============================================================================


class AnimatedProgressBar(QWidget):
    """Enhanced animated progress bar."""

    def __init__(
        self,
        color: str,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._colors = get_color_registry()
        self._color_str = color
        self._value = 0.0
        self._animation: Optional[QPropertyAnimation] = None

        self.setFixedHeight(6)
        self.setMinimumWidth(60)

        self._theme_service.themeChanged.connect(lambda _: self.update())

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, target: float) -> None:
        target = min(max(target, 0), 100)

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(AnimationDuration.SLOW)
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(target)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self._theme_service.tokens

        # Track
        track_color = self._colors.get_color(tokens.interactive_hover)
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(rect), 3, 3)
        painter.fillPath(track_path, track_color)

        # Fill
        if self._value > 0:
            fill_width = rect.width() * (self._value / 100)
            fill_rect = QRectF(0, 0, fill_width, rect.height())

            fill_color = self._colors.get_color(self._color_str)
            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())

            # FIXED: Always use valid gradient positions
            gradient.setColorAt(0.0, fill_color.lighter(115))
            gradient.setColorAt(0.5, fill_color)
            gradient.setColorAt(1.0, fill_color.darker(105))

            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 3, 3)
            painter.fillPath(fill_path, QBrush(gradient))

            # Shine effect
            if fill_width > 10:
                shine_rect = QRectF(0, 0, fill_width, rect.height() / 2)
                shine_gradient = QLinearGradient(shine_rect.topLeft(), shine_rect.bottomLeft())
                # FIXED: Always use valid gradient positions
                shine_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
                shine_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))

                shine_path = QPainterPath()
                shine_path.addRoundedRect(shine_rect, 3, 3)
                painter.fillPath(shine_path, QBrush(shine_gradient))


# ============================================================================
# Compact Stat Card
# ============================================================================


class CompactStatCard(QFrame):
    """Enhanced compact stat card with animations."""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        color: str,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._title = title
        self._color = color
        self._theme_service = theme_service
        self._current_value = "--"
        self._current_percent = 0.0

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Color indicator
        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 28)
        self._indicator.setStyleSheet(f"background-color: {self._color}; border-radius: 1px;")
        layout.addWidget(self._indicator)

        # Content
        content = QVBoxLayout()
        content.setSpacing(3)

        # Header row
        row = QHBoxLayout()
        row.setSpacing(6)

        self._title_label = QLabel(self._title)
        row.addWidget(self._title_label)

        self._value_label = QLabel("--")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._value_label)

        content.addLayout(row)

        # Progress bar
        self._progress = AnimatedProgressBar(self._color, self._theme_service)
        content.addWidget(self._progress)

        layout.addLayout(content, 1)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_style()

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            CompactStatCard {{
                background: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_base};
            }}
            CompactStatCard:hover {{
                border-color: {tokens.border_strong};
                background: {tokens.interactive_hover};
            }}
        """
        )

        self._title_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

        self._value_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_bold};
            color: {self._color};
        """
        )

    def set_data(self, value: str, percent: float) -> None:
        """Set data with animation."""
        self._current_value = value
        self._current_percent = percent

        self._value_label.setText(value)
        self._progress.animate_to(percent)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ============================================================================
# Single Device Gantt Bar
# ============================================================================


class SingleDeviceGanttBar(QWidget):
    """Enhanced interactive Gantt bar for single device."""

    segment_hovered = Signal(object)
    segment_clicked = Signal(object)

    def __init__(
        self,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._colors = get_color_registry()
        self._segments: List["GanttSegmentModel"] = []
        self._precomputed: List[Tuple[float, float, int, "GanttSegmentModel"]] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._hovered_index = -1

        # Animation
        self._hover_scale = 1.0

        self.setFixedHeight(36)
        self.setMouseTracking(True)

        self._theme_service.themeChanged.connect(lambda _: self.update())

    @property
    def tokens(self):
        return self._theme_service.tokens

    def set_data(
        self,
        segments: List["GanttSegmentModel"],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._segments = segments if segments else []
        self._start_time = start_time
        self._end_time = end_time
        self._precompute_geometry()
        self.update()

    def _precompute_geometry(self) -> None:
        """Pre-compute segment geometry with proper clipping."""
        self._precomputed.clear()

        if not self._segments or not self._start_time or not self._end_time:
            return

        rect = self.rect()
        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        for seg in self._segments:
            # FIXED: Clip segment to window bounds
            clipped_start = max(seg.start_time, self._start_time)
            clipped_end = min(seg.end_time, self._end_time)

            # Skip if segment is outside window
            if clipped_start >= clipped_end:
                continue

            # Calculate offsets from clipped times (always >= 0)
            start_offset = (clipped_start - self._start_time).total_seconds()
            end_offset = (clipped_end - self._start_time).total_seconds()

            # Ensure non-negative
            start_offset = max(0, start_offset)
            end_offset = max(start_offset, end_offset)

            x = (start_offset / total_seconds) * rect.width()
            width = max(((end_offset - start_offset) / total_seconds) * rect.width(), 3)

            self._precomputed.append((x, width, seg.status_code, seg))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self.tokens

        # Track background
        track_color = self._colors.get_color(tokens.interactive_hover)
        track_rect = QRectF(0, 6, rect.width(), rect.height() - 12)

        track_path = QPainterPath()
        track_path.addRoundedRect(track_rect, 5, 5)
        painter.fillPath(track_path, track_color)

        if not self._precomputed:
            # Empty state
            font = self._colors.get_font(tokens.font_family, 9)
            painter.setPen(self._colors.get_color(tokens.text_muted))
            painter.setFont(font)
            painter.drawText(track_rect, Qt.AlignmentFlag.AlignCenter, "No data available")
            return

        # Draw segments
        for i, (x, width, status_code, seg) in enumerate(self._precomputed):
            is_hovered = i == self._hovered_index

            # Calculate rect with hover effect
            y = 6
            height = rect.height() - 12
            if is_hovered:
                y -= 2
                height += 4

            seg_rect = QRectF(x, y, width, height)

            # Gradient colors
            start_color, end_color = self._colors.get_status_gradient_colors(status_code)

            if is_hovered:
                start_color = start_color.lighter(115)
                end_color = end_color.lighter(110)

            gradient = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
            # FIXED: Always use valid gradient positions
            gradient.setColorAt(0.0, start_color)
            gradient.setColorAt(1.0, end_color)

            path = QPainterPath()
            path.addRoundedRect(seg_rect, 4, 4)
            painter.fillPath(path, QBrush(gradient))

            # Current segment indicator
            if seg.is_current:
                painter.setPen(QPen(QColor("#FFFFFF"), 2))
                painter.drawPath(path)

            # Hover border
            if is_hovered:
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                painter.drawPath(path)

        # Now indicator
        self._draw_now_indicator(painter, rect)

    def _draw_now_indicator(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return
        if not (self._start_time <= now <= self._end_time):
            return

        total_seconds = (self._end_time - self._start_time).total_seconds()
        now_offset = (now - self._start_time).total_seconds()

        # FIXED: Clamp position to valid range
        position_ratio = clamp(now_offset / total_seconds, 0.0, 1.0)
        x = position_ratio * rect.width()

        error_color = self._colors.get_color(self.tokens.error)

        # Line
        painter.setPen(QPen(error_color, 2))
        painter.drawLine(int(x), 2, int(x), int(rect.height() - 2))

        # Diamond marker
        painter.setBrush(QBrush(error_color))
        painter.setPen(Qt.PenStyle.NoPen)

        marker_path = QPainterPath()
        marker_path.moveTo(x, 0)
        marker_path.lineTo(x + 5, 5)
        marker_path.lineTo(x, 10)
        marker_path.lineTo(x - 5, 5)
        marker_path.closeSubpath()
        painter.drawPath(marker_path)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        new_index = self._hit_test(pos)

        if new_index != self._hovered_index:
            self._hovered_index = new_index
            self.update()

            if 0 <= new_index < len(self._precomputed):
                _, _, _, seg = self._precomputed[new_index]
                self.segment_hovered.emit(seg)

                tooltip = f"<b>{seg.status_name}</b><br>" f"Duration: {seg.duration_display}<br>" f"{seg.start_display} → {seg.end_display}"
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    tooltip,
                    self,
                )
            else:
                QToolTip.hideText()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._hit_test(event.position())
            if 0 <= index < len(self._precomputed):
                _, _, _, seg = self._precomputed[index]
                self.segment_clicked.emit(seg)

    def leaveEvent(self, event) -> None:
        self._hovered_index = -1
        self.update()
        QToolTip.hideText()

    def _hit_test(self, pos: QPointF) -> int:
        if not self._precomputed:
            return -1

        x_pos = pos.x()
        for i, (x, width, _, _) in enumerate(self._precomputed):
            if x <= x_pos <= x + width:
                return i

        return -1

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._precompute_geometry()


# ============================================================================
# Device Gantt Widget (Full Panel)
# ============================================================================


class DeviceGanttWidget(QFrame):
    """Enhanced single-device Gantt chart widget for right panel."""

    segment_clicked = Signal(str, object)

    def __init__(
        self,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._chart_model: Optional["GanttChartModel"] = None
        self._is_loading = True

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Stats grid
        self._stats_container = self._create_stats_section()
        layout.addWidget(self._stats_container)

        # Timeline section
        timeline_section = self._create_timeline_section()
        layout.addWidget(timeline_section)

        # Legend
        legend = self._create_legend()
        layout.addWidget(legend)

        # Loading overlay
        self._loading_skeleton = self._create_loading_skeleton()
        layout.addWidget(self._loading_skeleton)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Device icon placeholder
        self._device_icon = QLabel()
        self._device_icon.setFixedSize(32, 32)
        header_layout.addWidget(self._device_icon)

        # Device info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._device_code_label = QLabel("--")
        self._device_code_label.setObjectName("device_code")
        info_layout.addWidget(self._device_code_label)

        self._device_name_label = QLabel("")
        self._device_name_label.setObjectName("device_name")
        info_layout.addWidget(self._device_name_label)

        header_layout.addLayout(info_layout, 1)

        # Status badge
        self._status_badge = QLabel("--")
        self._status_badge.setObjectName("status_badge")
        header_layout.addWidget(self._status_badge)

        return header

    def _create_stats_section(self) -> QWidget:
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        tokens = self._theme_service.tokens

        self._running_card = CompactStatCard("Running", tokens.success, self._theme_service)
        self._stopped_card = CompactStatCard("Stopped", tokens.warning, self._theme_service)
        self._alarm_card = CompactStatCard("Alarm", tokens.error, self._theme_service)
        self._oee_card = CompactStatCard("OEE", tokens.primary, self._theme_service)

        layout.addWidget(self._running_card, 0, 0)
        layout.addWidget(self._stopped_card, 0, 1)
        layout.addWidget(self._alarm_card, 1, 0)
        layout.addWidget(self._oee_card, 1, 1)

        return container

    def _create_timeline_section(self) -> QWidget:
        container = QFrame()
        container.setObjectName("timeline_container")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Title row
        title_row = QHBoxLayout()

        title = QLabel("📊 24h Timeline")
        title.setObjectName("timeline_title")
        title_row.addWidget(title)

        title_row.addStretch()

        # Refresh button
        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(24, 24)
        self._refresh_btn.setToolTip("Refresh timeline")
        title_row.addWidget(self._refresh_btn)

        layout.addLayout(title_row)

        # Gantt bar
        self._gantt_bar = SingleDeviceGanttBar(self._theme_service)
        self._gantt_bar.segment_clicked.connect(self._on_segment_clicked)
        layout.addWidget(self._gantt_bar)

        # Time labels
        time_labels = QHBoxLayout()
        time_labels.setContentsMargins(0, 0, 0, 0)

        self._start_label = QLabel("00:00")
        self._start_label.setObjectName("time_label")

        self._mid_label = QLabel("12:00")
        self._mid_label.setObjectName("time_label")
        self._mid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._end_label = QLabel("Now")
        self._end_label.setObjectName("time_label")
        self._end_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_labels.addWidget(self._start_label)
        time_labels.addWidget(self._mid_label, 1)
        time_labels.addWidget(self._end_label)
        layout.addLayout(time_labels)

        return container

    def _create_legend(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        statuses = [
            ("Running", "#2ECC71"),
            ("Stopped", "#E74C3C"),
            ("Alarm", "#F1C40F"),
            ("Maint", "#9B59B6"),
            ("Off", "#7F8C8D"),
        ]

        for name, color in statuses:
            item = QHBoxLayout()
            item.setSpacing(4)

            dot = QFrame()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"""
                background: {color}; 
                border-radius: 4px;
                border: 1px solid rgba(255,255,255,0.2);
            """
            )
            item.addWidget(dot)

            label = QLabel(name)
            label.setObjectName("legend_label")
            item.addWidget(label)

            layout.addLayout(item)

        layout.addStretch()

        return container

    def _create_loading_skeleton(self) -> QWidget:
        """Create loading skeleton."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header skeleton
        header_skel = QHBoxLayout()
        header_skel.addWidget(SkeletonLoader(32, 32))

        text_col = QVBoxLayout()
        text_col.addWidget(SkeletonLoader(100, 16))
        text_col.addWidget(SkeletonLoader(60, 12))
        header_skel.addLayout(text_col, 1)
        header_skel.addWidget(SkeletonLoader(60, 24))

        layout.addLayout(header_skel)

        # Stats skeleton
        stats_grid = QGridLayout()
        for i in range(2):
            for j in range(2):
                stats_grid.addWidget(SkeletonLoader(100, 50), i, j)
        layout.addLayout(stats_grid)

        # Timeline skeleton
        layout.addWidget(SkeletonLoader(0, 40))  # Full width

        container.hide()
        return container

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_style()

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            DeviceGanttWidget {{
                background: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_lg};
            }}
        """
        )

        self._device_code_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_lg};
            font-weight: {tokens.font_weight_bold};
            color: {tokens.text_primary};
        """
        )

        self._device_name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

        self._status_badge.setStyleSheet(
            f"""
            padding: 4px 10px;
            border-radius: {tokens.radius_full};
            font-size: {tokens.font_size_xs};
            font-weight: {tokens.font_weight_semibold};
            background: {tokens.text_muted};
            color: {tokens.text_inverse};
        """
        )

        # Timeline container
        timeline = self.findChild(QFrame, "timeline_container")
        if timeline:
            timeline.setStyleSheet(
                f"""
                QFrame#timeline_container {{
                    background: {tokens.surface_app};
                    border: 1px solid {tokens.border_default};
                    border-radius: {tokens.radius_md};
                }}
            """
            )

        # Labels
        title = self.findChild(QLabel, "timeline_title")
        if title:
            title.setStyleSheet(
                f"""
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_semibold};
                color: {tokens.text_secondary};
            """
            )

        for label in self.findChildren(QLabel, "time_label"):
            label.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                color: {tokens.text_muted};
            """
            )

        for label in self.findChildren(QLabel, "legend_label"):
            label.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                color: {tokens.text_muted};
            """
            )

        # Refresh button
        self._refresh_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {tokens.interactive_hover};
            }}
        """
        )

    def set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        self._is_loading = loading

        if loading:
            self._stats_container.hide()
            self._loading_skeleton.show()
        else:
            self._loading_skeleton.hide()
            self._stats_container.show()

    def render(self, chart_model: "GanttChartModel") -> None:
        """Render chart with animation."""
        self._chart_model = chart_model
        tokens = self._theme_service.tokens

        # Hide loading
        self.set_loading(False)

        # Update header
        self._device_code_label.setText(chart_model.device_code)

        if hasattr(chart_model, "device_name"):
            self._device_name_label.setText(chart_model.device_name)
            self._device_name_label.show()
        else:
            self._device_name_label.hide()

        # Status badge with color
        self._status_badge.setText(chart_model.current_status.upper())
        self._status_badge.setStyleSheet(
            f"""
            padding: 4px 10px;
            border-radius: {tokens.radius_full};
            font-size: {tokens.font_size_xs};
            font-weight: {tokens.font_weight_semibold};
            background: {chart_model.current_status_color};
            color: {tokens.text_inverse};
        """
        )

        # Stats with animation
        stats = chart_model.stats
        self._running_card.set_data(stats.running_display, stats.running_percent)
        self._stopped_card.set_data(stats.stopped_display, stats.stopped_percent)
        self._alarm_card.set_data(stats.alarm_display, stats.alarm_percent)
        self._oee_card.set_data(f"{stats.oee_estimate:.0f}%", stats.oee_estimate)

        # Gantt bar
        self._gantt_bar.set_data(
            chart_model.segments,
            chart_model.start_time,
            chart_model.end_time,
        )

        # Time labels
        self._start_label.setText(chart_model.start_time.strftime("%H:%M"))

        mid_time = chart_model.start_time + (chart_model.end_time - chart_model.start_time) / 2
        self._mid_label.setText(mid_time.strftime("%H:%M"))

        self._end_label.setText(chart_model.end_time.strftime("%H:%M"))

    def _on_segment_clicked(self, segment: "GanttSegmentModel") -> None:
        if self._chart_model:
            self.segment_clicked.emit(self._chart_model.device_code, segment)


__all__ = [
    "GanttCanvasWidget",
    "DeviceGanttWidget",
    "AnimatedProgressBar",
    "CompactStatCard",
    "SingleDeviceGanttBar",
    "PrecomputedSegment",
    "STATUS_GRADIENTS",
]
