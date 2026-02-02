# File: presentation/views/widgets/gantt_canvas.py
"""
Gantt Canvas Widget - MVVM Architecture.

Multi-device and single-device Gantt chart components.
Uses ThemeService for consistent theming.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
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
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...constants.status import Status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels.models.gantt_model import (
        GanttSegmentModel,
        GanttChartModel,
        GanttStatsModel,
    )

logger = logging.getLogger(__name__)


# Status gradient colors for gantt bars
STATUS_GRADIENTS = {
    0: ("#9E9E9E", "#757575"),  # Unknown
    1: ("#34D399", "#059669"),  # Running
    2: ("#94A3B8", "#64748B"),  # Shutdown
    3: ("#F87171", "#DC2626"),  # Stopped
    4: ("#A78BFA", "#7C3AED"),  # Maintenance
    5: ("#FBBF24", "#D97706"),  # Alarm
}


# =============================================================================
# Compact Multi-Device Bar Chart
# =============================================================================


class GanttCanvasWidget(QWidget):
    """
    Compact stacked bar chart showing multiple devices.

    Layout:
    - Left: Device labels (compact)
    - Right: Stacked horizontal bars with shared timeline
    - Bottom: Time ruler
    """

    device_clicked = Signal(str)

    LABEL_WIDTH = 70
    RULER_HEIGHT = 14
    BAR_HEIGHT = 8
    BAR_SPACING = 2
    MAX_DEVICES = 5

    def __init__(self, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None, is_compact: bool = False):
        super().__init__(parent)

        # Get theme service
        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._timeline_data: Dict[str, List[Dict[str, Any]]] = {}
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._is_compact = is_compact

        self.setMinimumHeight(40)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Connect to theme changes
        self._theme_service.themeChanged.connect(self._on_theme_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self.update()

    @property
    def tokens(self):
        """Get current theme tokens."""
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark

    def render_timeline(
        self,
        data: Dict[str, List[Any]],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """Render the compact multi-device timeline."""
        self._timeline_data = data if data else {}

        if not end:
            end = datetime.now()
        if not start:
            start = end - timedelta(hours=24)

        self._start_time = start
        self._end_time = end

        logger.debug(f"GanttCanvas: rendering {len(self._timeline_data)} devices")
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self.tokens

        # Colors from theme
        bg_color = QColor(tokens.surface_app)
        text_color = QColor(tokens.text_muted)
        grid_color = QColor(tokens.border_default)
        track_color = QColor(tokens.interactive_hover)

        # Background
        painter.fillRect(rect, bg_color)

        # If no data, show placeholder
        if not self._timeline_data or not self._start_time or not self._end_time:
            painter.setPen(text_color)
            painter.setFont(QFont(tokens.font_family, 9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "📊 Loading timeline...")
            return

        # Calculate layout
        num_devices = min(len(self._timeline_data), self.MAX_DEVICES)
        available_height = rect.height() - self.RULER_HEIGHT - 4

        if num_devices > 0 and available_height > 0:
            bar_height = max(
                4,
                min(
                    self.BAR_HEIGHT,
                    (available_height - (num_devices - 1) * self.BAR_SPACING) // num_devices,
                ),
            )
        else:
            bar_height = self.BAR_HEIGHT

        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10

        if chart_width <= 0:
            return

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        # Draw device bars
        y = 4
        painter.setFont(QFont("Consolas", 8))

        device_items = list(self._timeline_data.items())[: self.MAX_DEVICES]

        for device_code, segments in device_items:
            if y + bar_height > available_height + 4:
                break

            # Device label
            painter.setPen(text_color)
            label_rect = QRectF(4, y, self.LABEL_WIDTH - 8, bar_height)
            display_label = device_code[:8] if len(device_code) > 8 else device_code
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, display_label)

            # Bar track background
            bar_rect = QRectF(chart_left, y, chart_width, bar_height)
            painter.fillRect(bar_rect, track_color)

            # Draw segments
            if segments:
                for seg in segments:
                    self._draw_segment(painter, seg, chart_left, y, chart_width, bar_height, total_seconds)

            y += bar_height + self.BAR_SPACING

        # Draw time ruler at bottom
        ruler_y = rect.height() - self.RULER_HEIGHT
        self._draw_ruler(painter, rect, chart_left, chart_width, ruler_y, total_seconds, text_color, grid_color)

    def _draw_segment(
        self,
        painter: QPainter,
        seg: Any,
        chart_left: float,
        y: float,
        chart_width: float,
        bar_height: float,
        total_seconds: float,
    ) -> None:
        """Draw a single segment."""
        # Get segment data
        if isinstance(seg, dict):
            seg_start = seg.get("start_time")
            seg_end = seg.get("end_time")
            status_code = seg.get("status_code", 0)
        else:
            seg_start = getattr(seg, "start_time", None)
            seg_end = getattr(seg, "end_time", None)
            status_code = getattr(seg, "status_code", 0)

        if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
            return

        if seg_end < self._start_time or seg_start > self._end_time:
            return

        # Clip to window
        clipped_start = max(seg_start, self._start_time)
        clipped_end = min(seg_end, self._end_time)

        start_offset = (clipped_start - self._start_time).total_seconds()
        end_offset = (clipped_end - self._start_time).total_seconds()

        if end_offset <= start_offset:
            return

        x = chart_left + (start_offset / total_seconds) * chart_width
        width = max(((end_offset - start_offset) / total_seconds) * chart_width, 2)

        status_code = int(status_code) if status_code else 0
        color = QColor(Status.get_color(status_code))

        seg_rect = QRectF(x, y, width, bar_height)
        painter.fillRect(seg_rect, color)

    def _draw_ruler(
        self,
        painter: QPainter,
        rect: QRectF,
        chart_left: float,
        chart_width: float,
        ruler_y: float,
        total_seconds: float,
        text_color: QColor,
        grid_color: QColor,
    ) -> None:
        """Draw time ruler at bottom."""
        tokens = self.tokens
        painter.setFont(QFont("Consolas", 7))

        # Draw ruler line
        painter.setPen(QPen(grid_color, 1))
        painter.drawLine(int(chart_left), int(ruler_y), int(chart_left + chart_width), int(ruler_y))

        # Hour marks
        current = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current < self._start_time:
            current += timedelta(hours=1)

        while current <= self._end_time:
            offset = (current - self._start_time).total_seconds()
            x = chart_left + (offset / total_seconds) * chart_width

            if x < chart_left or x > chart_left + chart_width:
                current += timedelta(hours=1)
                continue

            # Tick mark
            painter.setPen(QPen(grid_color, 1))
            tick_height = 4 if current.hour % 6 == 0 else 2
            painter.drawLine(int(x), int(ruler_y), int(x), int(ruler_y + tick_height))

            # Label every 6 hours
            if current.hour % 6 == 0:
                painter.setPen(text_color)
                time_str = current.strftime("%H:%M")
                painter.drawText(int(x) - 15, int(ruler_y + 4), 30, 10, Qt.AlignmentFlag.AlignCenter, time_str)

            current += timedelta(hours=1)

    def mouseMoveEvent(self, event) -> None:
        """Handle hover for tooltip."""
        if not self._timeline_data or not self._start_time or not self._end_time:
            return

        pos = event.position()
        rect = self.rect()

        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10
        available_height = rect.height() - self.RULER_HEIGHT - 4

        num_devices = min(len(self._timeline_data), self.MAX_DEVICES)
        if num_devices <= 0 or available_height <= 0:
            return

        bar_height = max(
            4,
            min(
                self.BAR_HEIGHT,
                (available_height - (num_devices - 1) * self.BAR_SPACING) // num_devices,
            ),
        )

        # Find which device row
        y = 4
        for device_code, segments in list(self._timeline_data.items())[: self.MAX_DEVICES]:
            if y + bar_height > available_height + 4:
                break

            if y <= pos.y() <= y + bar_height and pos.x() >= chart_left:
                tooltip = self._find_segment_tooltip(device_code, segments, pos.x(), chart_left, chart_width)
                if tooltip:
                    QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
                    return

            y += bar_height + self.BAR_SPACING

        QToolTip.hideText()

    def _find_segment_tooltip(
        self,
        device_code: str,
        segments: List[Any],
        x_pos: float,
        chart_left: float,
        chart_width: float,
    ) -> Optional[str]:
        """Find segment at x position and return tooltip."""
        if not segments:
            return f"📍 {device_code}\nNo data"

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return None

        for seg in segments:
            if isinstance(seg, dict):
                seg_start = seg.get("start_time")
                seg_end = seg.get("end_time")
                status_code = seg.get("status_code", 0)
            else:
                seg_start = getattr(seg, "start_time", None)
                seg_end = getattr(seg, "end_time", None)
                status_code = getattr(seg, "status_code", 0)

            if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
                continue

            clipped_start = max(seg_start, self._start_time)
            clipped_end = min(seg_end, self._end_time)

            start_offset = (clipped_start - self._start_time).total_seconds()
            end_offset = (clipped_end - self._start_time).total_seconds()

            x_start = chart_left + (start_offset / total_seconds) * chart_width
            x_end = chart_left + (end_offset / total_seconds) * chart_width

            if x_start <= x_pos <= x_end:
                status_code = int(status_code) if status_code else 0
                status_name = Status.get_name(status_code)

                duration = (seg_end - seg_start).total_seconds()
                duration_str = self._format_duration(duration)
                time_range = f"{seg_start.strftime('%H:%M')} - {seg_end.strftime('%H:%M')}"

                return f"📍 {device_code}\n{status_name}: {duration_str}\n⏰ {time_range}"

        return f"📍 {device_code}"

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m = int(seconds) // 60
            return f"{m}m"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def mousePressEvent(self, event) -> None:
        """Handle click to select device."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not self._timeline_data:
            return

        pos = event.position()
        rect = self.rect()
        available_height = rect.height() - self.RULER_HEIGHT - 4

        num_devices = min(len(self._timeline_data), self.MAX_DEVICES)
        if num_devices <= 0 or available_height <= 0:
            return

        bar_height = max(
            4,
            min(
                self.BAR_HEIGHT,
                (available_height - (num_devices - 1) * self.BAR_SPACING) // num_devices,
            ),
        )

        y = 4
        for device_code in list(self._timeline_data.keys())[: self.MAX_DEVICES]:
            if y + bar_height > available_height + 4:
                break

            if y <= pos.y() <= y + bar_height:
                self.device_clicked.emit(device_code)
                logger.debug(f"Device clicked: {device_code}")
                return

            y += bar_height + self.BAR_SPACING


# =============================================================================
# Animated Progress Bar (for stat cards)
# =============================================================================


class AnimatedProgressBar(QWidget):
    """Animated progress bar for statistics."""

    def __init__(self, color: str, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._color = QColor(color)
        self._value = 0.0
        self._animation: Optional[QPropertyAnimation] = None

        self.setFixedHeight(4)
        self.setMinimumWidth(60)

        self._theme_service.themeChanged.connect(lambda _: self.update())

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, target: float) -> None:
        """Animate to target value."""
        target = min(max(target, 0), 100)

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(500)
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
        track_color = QColor(tokens.interactive_hover)
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 2, 2)

        # Fill
        if self._value > 0:
            fill_width = rect.width() * (self._value / 100)
            fill_rect = QRectF(0, 0, fill_width, rect.height())

            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            gradient.setColorAt(0, self._color.lighter(110))
            gradient.setColorAt(1, self._color)

            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill_rect, 2, 2)


# =============================================================================
# Compact Stat Card
# =============================================================================


class CompactStatCard(QFrame):
    """Compact stat card for right panel."""

    def __init__(self, title: str, color: str, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._title = title
        self._color = color
        self._theme_service = theme_service

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Color indicator
        indicator = QFrame()
        indicator.setFixedSize(3, 24)
        indicator.setStyleSheet(f"background-color: {self._color}; border-radius: 1px;")
        layout.addWidget(indicator)

        # Content
        content = QVBoxLayout()
        content.setSpacing(2)

        # Title and value row
        row = QHBoxLayout()
        row.setSpacing(4)

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
        """Update the stat value and progress."""
        self._value_label.setText(value)
        self._progress.animate_to(percent)


# =============================================================================
# Single Device Gantt Bar
# =============================================================================


class SingleDeviceGanttBar(QWidget):
    """Interactive Gantt bar for single device."""

    segment_hovered = Signal(object)
    segment_clicked = Signal(object)

    def __init__(self, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._segments: List["GanttSegmentModel"] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._hovered_index = -1

        self.setFixedHeight(32)
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
        """Set segment data."""
        self._segments = segments if segments else []
        self._start_time = start_time
        self._end_time = end_time
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self.tokens

        # Track background
        track_color = QColor(tokens.interactive_hover)
        track_rect = QRectF(0, 4, rect.width(), rect.height() - 8)

        path = QPainterPath()
        path.addRoundedRect(track_rect, 4, 4)
        painter.fillPath(path, track_color)

        if not self._segments or not self._start_time or not self._end_time:
            painter.setPen(QColor(tokens.text_muted))
            painter.setFont(QFont(tokens.font_family, 9))
            painter.drawText(track_rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        # Draw segments
        for i, seg in enumerate(self._segments):
            self._draw_segment(painter, seg, rect, total_seconds, i == self._hovered_index)

        # Draw now indicator
        self._draw_now_indicator(painter, rect, total_seconds)

    def _draw_segment(
        self,
        painter: QPainter,
        seg: "GanttSegmentModel",
        rect: QRectF,
        total_seconds: float,
        is_hovered: bool,
    ) -> None:
        """Draw a single segment."""
        start_offset = (seg.start_time - self._start_time).total_seconds()
        end_offset = (seg.end_time - self._start_time).total_seconds()

        x = (start_offset / total_seconds) * rect.width()
        width = max(((end_offset - start_offset) / total_seconds) * rect.width(), 2)

        y = 4
        height = rect.height() - 8

        if is_hovered:
            y -= 1
            height += 2

        seg_rect = QRectF(x, y, width, height)

        # Gradient
        gradient = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
        base_color = QColor(seg.gradient_start or seg.status_color)
        end_color = QColor(seg.gradient_end or seg.status_color)

        if is_hovered:
            base_color = base_color.lighter(115)
            end_color = end_color.lighter(110)

        gradient.setColorAt(0, base_color)
        gradient.setColorAt(1, end_color)

        path = QPainterPath()
        path.addRoundedRect(seg_rect, 3, 3)
        painter.fillPath(path, QBrush(gradient))

        # Current indicator
        if seg.is_current:
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawPath(path)

    def _draw_now_indicator(
        self,
        painter: QPainter,
        rect: QRectF,
        total_seconds: float,
    ) -> None:
        """Draw current time indicator."""
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return
        if not (self._start_time <= now <= self._end_time):
            return

        now_offset = (now - self._start_time).total_seconds()
        x = (now_offset / total_seconds) * rect.width()

        tokens = self.tokens

        # Line
        painter.setPen(QPen(QColor(tokens.error), 1.5))
        painter.drawLine(int(x), 2, int(x), int(rect.height() - 2))

        # Triangle marker
        painter.setBrush(QBrush(QColor(tokens.error)))
        painter.setPen(Qt.PenStyle.NoPen)

        marker_path = QPainterPath()
        marker_path.moveTo(x, 0)
        marker_path.lineTo(x + 4, 4)
        marker_path.lineTo(x - 4, 4)
        marker_path.closeSubpath()
        painter.drawPath(marker_path)

    def mouseMoveEvent(self, event) -> None:
        """Handle hover."""
        pos = event.position()
        new_index = self._hit_test(pos)

        if new_index != self._hovered_index:
            self._hovered_index = new_index
            self.update()

            if 0 <= new_index < len(self._segments):
                seg = self._segments[new_index]
                self.segment_hovered.emit(seg)
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{seg.status_name}\n{seg.duration_display}\n" f"{seg.start_display} - {seg.end_display}",
                    self,
                )

    def mousePressEvent(self, event) -> None:
        """Handle click."""
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._hit_test(event.position())
            if 0 <= index < len(self._segments):
                self.segment_clicked.emit(self._segments[index])

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        self._hovered_index = -1
        self.update()

    def _hit_test(self, pos: QPointF) -> int:
        """Find segment at position."""
        if not self._segments or not self._start_time or not self._end_time:
            return -1

        rect = self.rect()
        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return -1

        x_pos = pos.x()

        for i, seg in enumerate(self._segments):
            start_offset = (seg.start_time - self._start_time).total_seconds()
            end_offset = (seg.end_time - self._start_time).total_seconds()

            x_start = (start_offset / total_seconds) * rect.width()
            x_end = (end_offset / total_seconds) * rect.width()

            if x_start <= x_pos <= x_end:
                return i

        return -1


# =============================================================================
# Device Gantt Widget (Single device detail)
# =============================================================================


class DeviceGanttWidget(QFrame):
    """
    Single-device Gantt chart widget for right panel.
    """

    segment_clicked = Signal(str, object)

    def __init__(self, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._chart_model: Optional["GanttChartModel"] = None

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

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

    def _create_header(self) -> QWidget:
        """Create header with device code and status."""
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._device_code_label = QLabel("--")
        header_layout.addWidget(self._device_code_label)

        header_layout.addStretch()

        self._status_badge = QLabel("--")
        header_layout.addWidget(self._status_badge)

        return header

    def _create_stats_section(self) -> QWidget:
        """Create stats cards grid."""
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

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
        """Create timeline section with gantt bar."""
        container = QFrame()
        container.setObjectName("timeline_container")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title = QLabel("📊 24h Timeline")
        title.setObjectName("timeline_title")
        layout.addWidget(title)

        self._gantt_bar = SingleDeviceGanttBar(self._theme_service)
        self._gantt_bar.segment_clicked.connect(self._on_segment_clicked)
        layout.addWidget(self._gantt_bar)

        # Time labels
        time_labels = QHBoxLayout()
        time_labels.setContentsMargins(0, 0, 0, 0)

        self._start_label = QLabel("00:00")
        self._start_label.setObjectName("time_label")

        self._end_label = QLabel("Now")
        self._end_label.setObjectName("time_label")
        self._end_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        time_labels.addWidget(self._start_label)
        time_labels.addStretch()
        time_labels.addWidget(self._end_label)
        layout.addLayout(time_labels)

        return container

    def _create_legend(self) -> QWidget:
        """Create status legend."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(10)

        statuses = [
            ("Run", "#2ECC71"),
            ("Stop", "#E74C3C"),
            ("Alarm", "#F1C40F"),
            ("Maint", "#9B59B6"),
            ("Shut", "#7F8C8D"),
        ]

        for name, color in statuses:
            item = QHBoxLayout()
            item.setSpacing(3)

            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
            item.addWidget(dot)

            label = QLabel(name)
            label.setObjectName("legend_label")
            item.addWidget(label)

            layout.addLayout(item)

        layout.addStretch()

        return container

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply theme styles."""
        tokens = self._theme_service.tokens

        # Main frame
        self.setStyleSheet(
            f"""
            DeviceGanttWidget {{
                background: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_lg};
            }}
        """
        )

        # Device code label
        self._device_code_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_md};
            font-weight: {tokens.font_weight_bold};
            color: {tokens.text_primary};
        """
        )

        # Status badge
        self._status_badge.setStyleSheet(
            f"""
            padding: 3px 8px;
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
                    border-radius: {tokens.radius_base};
                }}
            """
            )

        # Timeline title
        title = self.findChild(QLabel, "timeline_title")
        if title:
            title.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_semibold};
                color: {tokens.text_muted};
            """
            )

        # Time labels
        for label in self.findChildren(QLabel, "time_label"):
            label.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                color: {tokens.text_muted};
            """
            )

        # Legend labels
        for label in self.findChildren(QLabel, "legend_label"):
            label.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                color: {tokens.text_muted};
            """
            )

    def render(self, chart_model: "GanttChartModel") -> None:
        """Render from GanttChartModel."""
        self._chart_model = chart_model
        tokens = self._theme_service.tokens

        # Header
        self._device_code_label.setText(chart_model.device_code)

        self._status_badge.setText(chart_model.current_status.upper())
        self._status_badge.setStyleSheet(
            f"""
            padding: 3px 8px;
            border-radius: {tokens.radius_full};
            font-size: {tokens.font_size_xs};
            font-weight: {tokens.font_weight_semibold};
            background: {chart_model.current_status_color};
            color: {tokens.text_inverse};
        """
        )

        # Stats
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
        self._end_label.setText(chart_model.end_time.strftime("%H:%M"))

    def _on_segment_clicked(self, segment: "GanttSegmentModel") -> None:
        """Handle segment click."""
        if self._chart_model:
            self.segment_clicked.emit(self._chart_model.device_code, segment)


__all__ = [
    "GanttCanvasWidget",
    "DeviceGanttWidget",
    "AnimatedProgressBar",
    "CompactStatCard",
    "SingleDeviceGanttBar",
    "STATUS_GRADIENTS",
]
