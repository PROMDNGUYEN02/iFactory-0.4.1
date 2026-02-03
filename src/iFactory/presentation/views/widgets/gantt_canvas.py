"""
Gantt Canvas Widget - Optimized for large datasets.

Key optimizations:
1. Viewport culling - only draw visible segments
2. ColorRegistry - no per-frame QColor allocation
3. Geometry precomputation - no math in paintEvent
4. Font caching - reuse QFont objects
5. Batch rendering for segments
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

from ...constants.colors import get_color_registry, ColorRegistry
from ...constants.status import Status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels.models.gantt_model import (
        GanttSegmentModel,
        GanttChartModel,
        GanttStatsModel,
    )

logger = logging.getLogger(__name__)

STATUS_GRADIENTS = ColorRegistry.STATUS_GRADIENTS


class PrecomputedSegment:
    """Pre-computed segment geometry for fast rendering."""

    __slots__ = ("x", "width", "status_code", "status_name", "start_time", "end_time", "duration_seconds")

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


class GanttCanvasWidget(QWidget):
    """
    Compact stacked bar chart showing multiple devices.

    OPTIMIZATIONS:
    - Viewport culling: skip segments outside visible area
    - Pre-computed geometry: all x/width calculated once in render_timeline
    - ColorRegistry: no QColor allocation in paintEvent
    - Cached fonts: reuse QFont objects
    """

    device_clicked = Signal(str)

    LABEL_WIDTH = 70
    RULER_HEIGHT = 14
    BAR_HEIGHT = 8
    BAR_SPACING = 2
    MAX_DEVICES = 5

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

        self.setMinimumHeight(40)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._theme_service.themeChanged.connect(self._on_theme_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self.update()

    @property
    def tokens(self):
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        return self._theme_service.is_dark

    def render_timeline(
        self,
        data: Dict[str, List[Any]],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> None:
        """
        Render timeline with geometry precomputation.

        All segment x/width values are calculated here, NOT in paintEvent.
        """
        self._precomputed_data.clear()
        self._device_order.clear()

        if not data:
            self._start_time = None
            self._end_time = None
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

        logger.debug(f"GanttCanvas: precomputed {len(self._device_order)} devices")
        self.update()

    def _precompute_segments(
        self,
        segments: List[Any],
        chart_width: float,
        total_seconds: float,
    ) -> List[PrecomputedSegment]:
        """Pre-compute segment geometry."""
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

            if seg_end < self._start_time or seg_start > self._end_time:
                continue

            clipped_start = max(seg_start, self._start_time)
            clipped_end = min(seg_end, self._end_time)

            start_offset = (clipped_start - self._start_time).total_seconds()
            end_offset = (clipped_end - self._start_time).total_seconds()

            if end_offset <= start_offset:
                continue

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

        if not self._precomputed_data or not self._start_time or not self._end_time:
            font = self._colors.get_font(tokens.font_family, 9)
            painter.setPen(text_color)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "📊 Loading timeline...")
            return

        num_devices = len(self._device_order)
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

        self._cached_bar_height = bar_height
        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10

        if chart_width <= 0:
            return

        visible_rect = QRectF(chart_left, 0, chart_width, rect.height())

        label_font = self._colors.get_font("Consolas", 8)
        painter.setFont(label_font)

        y = 4
        track_brush = QBrush(track_color)
        no_pen = QPen(Qt.PenStyle.NoPen)

        for device_code in self._device_order:
            if y + bar_height > available_height + 4:
                break

            painter.setPen(text_color)
            label_rect = QRectF(4, y, self.LABEL_WIDTH - 8, bar_height)
            display_label = device_code[:8] if len(device_code) > 8 else device_code
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                display_label,
            )

            bar_rect = QRectF(chart_left, y, chart_width, bar_height)
            painter.setPen(no_pen)
            painter.fillRect(bar_rect, track_brush)

            segments = self._precomputed_data.get(device_code, [])
            for seg in segments:
                seg_x = chart_left + seg.x
                if seg_x + seg.width < visible_rect.left():
                    continue
                if seg_x > visible_rect.right():
                    continue

                seg_rect = QRectF(seg_x, y, seg.width, bar_height)
                brush = self._colors.get_status_brush(seg.status_code)
                painter.fillRect(seg_rect, brush)

            y += bar_height + self.BAR_SPACING

        ruler_y = rect.height() - self.RULER_HEIGHT
        self._draw_ruler(painter, rect, chart_left, chart_width, ruler_y, text_color, grid_color)

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
        if not self._start_time or not self._end_time:
            return

        ruler_font = self._colors.get_font("Consolas", 7)
        painter.setFont(ruler_font)

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

            painter.setPen(grid_pen)
            tick_height = 4 if current.hour % 6 == 0 else 2
            painter.drawLine(int(x), int(ruler_y), int(x), int(ruler_y + tick_height))

            if current.hour % 6 == 0:
                painter.setPen(text_color)
                time_str = current.strftime("%H:%M")
                painter.drawText(int(x) - 15, int(ruler_y + 4), 30, 10, Qt.AlignmentFlag.AlignCenter, time_str)

            current += timedelta(hours=1)

    def mouseMoveEvent(self, event) -> None:
        if not self._precomputed_data or not self._start_time:
            return

        pos = event.position()
        rect = self.rect()

        chart_left = self.LABEL_WIDTH
        chart_width = rect.width() - self.LABEL_WIDTH - 10
        available_height = rect.height() - self.RULER_HEIGHT - 4

        bar_height = self._cached_bar_height

        y = 4
        for device_code in self._device_order:
            if y + bar_height > available_height + 4:
                break

            if y <= pos.y() <= y + bar_height and pos.x() >= chart_left:
                tooltip = self._find_segment_tooltip(device_code, pos.x(), chart_left)
                if tooltip:
                    QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
                    return

            y += bar_height + self.BAR_SPACING

        QToolTip.hideText()

    def _find_segment_tooltip(
        self,
        device_code: str,
        x_pos: float,
        chart_left: float,
    ) -> Optional[str]:
        segments = self._precomputed_data.get(device_code, [])
        if not segments:
            return f"📍 {device_code}\nNo data"

        for seg in segments:
            seg_x = chart_left + seg.x
            if seg_x <= x_pos <= seg_x + seg.width:
                duration_str = self._format_duration(seg.duration_seconds)
                time_range = f"{seg.start_time.strftime('%H:%M')} - " f"{seg.end_time.strftime('%H:%M')}"
                return f"📍 {device_code}\n{seg.status_name}: {duration_str}\n⏰ {time_range}"

        return f"📍 {device_code}"

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m = int(seconds) // 60
            return f"{m}m"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not self._device_order:
            return

        pos = event.position()
        rect = self.rect()
        available_height = rect.height() - self.RULER_HEIGHT - 4
        bar_height = self._cached_bar_height

        y = 4
        for device_code in self._device_order:
            if y + bar_height > available_height + 4:
                break

            if y <= pos.y() <= y + bar_height:
                self.device_clicked.emit(device_code)
                logger.debug(f"Device clicked: {device_code}")
                return

            y += bar_height + self.BAR_SPACING

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
                start_offset = (seg.start_time - self._start_time).total_seconds()
                end_offset = (seg.end_time - self._start_time).total_seconds()
                seg.x = (start_offset / self._total_seconds) * chart_width
                seg.width = max(((end_offset - start_offset) / self._total_seconds) * chart_width, 2)


class AnimatedProgressBar(QWidget):
    """Animated progress bar for statistics."""

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

        track_color = self._colors.get_color(tokens.interactive_hover)
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 2, 2)

        if self._value > 0:
            fill_width = rect.width() * (self._value / 100)
            fill_rect = QRectF(0, 0, fill_width, rect.height())

            fill_color = self._colors.get_color(self._color_str)
            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            gradient.setColorAt(0, fill_color.lighter(110))
            gradient.setColorAt(1, fill_color)

            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill_rect, 2, 2)


class CompactStatCard(QFrame):
    """Compact stat card for right panel."""

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

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        indicator = QFrame()
        indicator.setFixedSize(3, 24)
        indicator.setStyleSheet(f"background-color: {self._color}; border-radius: 1px;")
        layout.addWidget(indicator)

        content = QVBoxLayout()
        content.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(4)

        self._title_label = QLabel(self._title)
        row.addWidget(self._title_label)

        self._value_label = QLabel("--")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._value_label)

        content.addLayout(row)

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
        self._value_label.setText(value)
        self._progress.animate_to(percent)


class SingleDeviceGanttBar(QWidget):
    """Interactive Gantt bar for single device."""

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
        self._segments = segments if segments else []
        self._start_time = start_time
        self._end_time = end_time
        self._precompute_geometry()
        self.update()

    def _precompute_geometry(self) -> None:
        """Pre-compute segment geometry."""
        self._precomputed.clear()

        if not self._segments or not self._start_time or not self._end_time:
            return

        rect = self.rect()
        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        for seg in self._segments:
            start_offset = (seg.start_time - self._start_time).total_seconds()
            end_offset = (seg.end_time - self._start_time).total_seconds()

            x = (start_offset / total_seconds) * rect.width()
            width = max(((end_offset - start_offset) / total_seconds) * rect.width(), 2)

            self._precomputed.append((x, width, seg.status_code, seg))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self.tokens

        track_color = self._colors.get_color(tokens.interactive_hover)
        track_rect = QRectF(0, 4, rect.width(), rect.height() - 8)

        path = QPainterPath()
        path.addRoundedRect(track_rect, 4, 4)
        painter.fillPath(path, track_color)

        if not self._precomputed:
            font = self._colors.get_font(tokens.font_family, 9)
            painter.setPen(self._colors.get_color(tokens.text_muted))
            painter.setFont(font)
            painter.drawText(track_rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        for i, (x, width, status_code, seg) in enumerate(self._precomputed):
            is_hovered = i == self._hovered_index

            y = 4
            height = rect.height() - 8
            if is_hovered:
                y -= 1
                height += 2

            seg_rect = QRectF(x, y, width, height)

            start_color, end_color = self._colors.get_status_gradient_colors(status_code)

            if is_hovered:
                start_color = start_color.lighter(115)
                end_color = end_color.lighter(110)

            gradient = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
            gradient.setColorAt(0, start_color)
            gradient.setColorAt(1, end_color)

            path = QPainterPath()
            path.addRoundedRect(seg_rect, 3, 3)
            painter.fillPath(path, QBrush(gradient))

            if seg.is_current:
                painter.setPen(QPen(self._colors.get_color("#FFFFFF"), 1.5))
                painter.drawPath(path)

        self._draw_now_indicator(painter, rect)

    def _draw_now_indicator(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return
        if not (self._start_time <= now <= self._end_time):
            return

        total_seconds = (self._end_time - self._start_time).total_seconds()
        now_offset = (now - self._start_time).total_seconds()
        x = (now_offset / total_seconds) * rect.width()

        error_color = self._colors.get_color(self.tokens.error)

        painter.setPen(QPen(error_color, 1.5))
        painter.drawLine(int(x), 2, int(x), int(rect.height() - 2))

        painter.setBrush(QBrush(error_color))
        painter.setPen(Qt.PenStyle.NoPen)

        marker_path = QPainterPath()
        marker_path.moveTo(x, 0)
        marker_path.lineTo(x + 4, 4)
        marker_path.lineTo(x - 4, 4)
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
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{seg.status_name}\n{seg.duration_display}\n" f"{seg.start_display} - {seg.end_display}",
                    self,
                )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._hit_test(event.position())
            if 0 <= index < len(self._precomputed):
                _, _, _, seg = self._precomputed[index]
                self.segment_clicked.emit(seg)

    def leaveEvent(self, event) -> None:
        self._hovered_index = -1
        self.update()

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


class DeviceGanttWidget(QFrame):
    """Single-device Gantt chart widget for right panel."""

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

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = self._create_header()
        layout.addWidget(header)

        self._stats_container = self._create_stats_section()
        layout.addWidget(self._stats_container)

        timeline_section = self._create_timeline_section()
        layout.addWidget(timeline_section)

        legend = self._create_legend()
        layout.addWidget(legend)

    def _create_header(self) -> QWidget:
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
            font-size: {tokens.font_size_md};
            font-weight: {tokens.font_weight_bold};
            color: {tokens.text_primary};
        """
        )

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

        title = self.findChild(QLabel, "timeline_title")
        if title:
            title.setStyleSheet(
                f"""
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_semibold};
                color: {tokens.text_muted};
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

    def render(self, chart_model: "GanttChartModel") -> None:
        self._chart_model = chart_model
        tokens = self._theme_service.tokens

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

        stats = chart_model.stats
        self._running_card.set_data(stats.running_display, stats.running_percent)
        self._stopped_card.set_data(stats.stopped_display, stats.stopped_percent)
        self._alarm_card.set_data(stats.alarm_display, stats.alarm_percent)
        self._oee_card.set_data(f"{stats.oee_estimate:.0f}%", stats.oee_estimate)

        self._gantt_bar.set_data(
            chart_model.segments,
            chart_model.start_time,
            chart_model.end_time,
        )

        self._start_label.setText(chart_model.start_time.strftime("%H:%M"))
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
