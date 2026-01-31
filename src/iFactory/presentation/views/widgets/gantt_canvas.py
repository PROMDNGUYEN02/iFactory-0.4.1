"""
Professional Gantt Chart Canvas Widget.
Displays device status timeline for 24 hours with clear colors.
Supports Compact Mode for sidebar/summary views.
Refactored for Hybrid Dict/ViewModel Support.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Union

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QLinearGradient, QPainterPath
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QScrollArea, QFrame

from ...resources.themes.theme_manager import theme_manager
from ...constants.ui_constants import StatusColors

logger = logging.getLogger(__name__)


class GanttRowWidget(QWidget):
    ROW_HEIGHT = 32

    def __init__(self, equip_code: str, segments: List[Any], start_time: datetime, end_time: datetime, label_width: int = 90, parent=None):
        super().__init__(parent)
        self._equip_code = equip_code
        self._segments = segments
        self._start_time = start_time
        self._end_time = end_time
        self._label_width = label_width
        self._row_index = 0

        self._is_compact = label_width == 0
        height = 20 if self._is_compact else self.ROW_HEIGHT
        self.setFixedHeight(height)
        self.setMouseTracking(True)

    def set_row_index(self, index: int):
        self._row_index = index

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # [THEME] Dynamic background
        bg_base = theme_manager.get_qcolor("chart.bg")
        if not self._is_compact:
            if self._row_index % 2 == 0:
                bg_color = bg_base.lighter(105) if theme_manager.is_dark else bg_base.darker(105)
            else:
                bg_color = bg_base
            painter.fillRect(rect, bg_color)
        else:
            painter.fillRect(rect, Qt.transparent)

        # Draw Label and Grid
        if self._label_width > 0:
            painter.setPen(QPen(theme_manager.get_qcolor("chart.grid"), 1))
            painter.drawLine(self._label_width, rect.height() - 1, rect.width(), rect.height() - 1)

            painter.setPen(theme_manager.get_qcolor("chart.text"))
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            label_rect = QRectF(5, 0, self._label_width - 10, rect.height())
            painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._equip_code)

        # Draw segments
        chart_width = rect.width() - self._label_width - 10
        total_seconds = (self._end_time - self._start_time).total_seconds()

        y_pos = 0 if self._is_compact else 3
        bar_height = rect.height() if self._is_compact else (rect.height() - 6)

        if total_seconds > 0:
            for seg in self._segments:
                self._draw_segment(painter, seg, chart_width, total_seconds, y_pos, bar_height)

    def _get_val(self, obj, key):
        """Helper to get value from either dict or object."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def _draw_segment(self, painter, seg, chart_width, total_seconds, y, height):
        seg_start = self._get_val(seg, "start_time")
        seg_end = self._get_val(seg, "end_time")

        if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
            return

        # Clamp segment to window
        if seg_end < self._start_time or seg_start > self._end_time:
            return

        start_offset = max(0, (seg_start - self._start_time).total_seconds())
        end_offset = min(total_seconds, (seg_end - self._start_time).total_seconds())

        if end_offset <= start_offset:
            return

        x = self._label_width + (start_offset / total_seconds) * chart_width
        width = max(((end_offset - start_offset) / total_seconds) * chart_width, 2)

        status_code = int(self._get_val(seg, "status_code") or 0)
        base_color = QColor(StatusColors.get_color(status_code))

        rect = QRectF(x, y, width, height)

        if self._is_compact:
            painter.fillRect(rect, base_color)
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0, base_color.lighter(120))
            gradient.setColorAt(1, base_color)
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            painter.fillPath(path, QBrush(gradient))


class TimeRulerWidget(QWidget):
    def __init__(self, parent=None, is_compact=False):
        super().__init__(parent)
        now = datetime.now()
        self._start_time = now - timedelta(hours=24)
        self._end_time = now
        self._label_width = 0 if is_compact else 90
        self._is_compact = is_compact
        self.setFixedHeight(16 if is_compact else 28)

    def set_time_range(self, start, end, label_width=90):
        self._start_time = start
        self._end_time = end
        self._label_width = label_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, theme_manager.get_qcolor("chart.bg"))

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        painter.setFont(QFont("Consolas", 7 if self._is_compact else 8))
        grid_color = theme_manager.get_qcolor("chart.grid")
        text_color = theme_manager.get_qcolor("chart.text")

        right_pad = 0 if self._is_compact else 10
        chart_width = rect.width() - self._label_width - right_pad

        current_time = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current_time < self._start_time:
            current_time += timedelta(hours=1)

        step_hours = 4 if self._is_compact else 2

        while current_time <= self._end_time:
            seconds_from_start = (current_time - self._start_time).total_seconds()
            x = self._label_width + (seconds_from_start / total_seconds) * chart_width

            if self._label_width <= x <= rect.width():
                painter.setPen(QPen(grid_color, 1))
                line_height = 4 if self._is_compact else 6
                painter.drawLine(int(x), rect.height() - line_height, int(x), rect.height())

                if current_time.hour % step_hours == 0:
                    painter.setPen(text_color)
                    time_str = current_time.strftime("%H") if self._is_compact else current_time.strftime("%H:%M")
                    painter.drawText(int(x) - 15, 0, 30, rect.height(), Qt.AlignCenter, time_str)

            current_time += timedelta(hours=1)


class GanttCanvasWidget(QWidget):
    segment_clicked = Signal(str, dict)

    def __init__(self, parent=None, is_compact: bool = False):
        super().__init__(parent)
        self._timeline_data = {}
        self._is_compact = is_compact
        self.LABEL_WIDTH = 0 if is_compact else 90
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if not self._is_compact:
            self._header = QFrame()
            self._header.setFixedHeight(36)
            self._update_header_style()

            h_layout = QHBoxLayout(self._header)
            h_layout.setContentsMargins(10, 0, 10, 0)

            title = QLabel("📊 Production Timeline (Last 24h)")
            title.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 12px;")
            h_layout.addWidget(title)
            h_layout.addStretch()
            layout.addWidget(self._header)

        self._time_ruler = TimeRulerWidget(is_compact=self._is_compact)
        layout.addWidget(self._time_ruler)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff if self._is_compact else Qt.ScrollBarAsNeeded)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(1)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

    def _update_header_style(self):
        if not hasattr(self, "_header"):
            return
        if theme_manager.is_dark:
            grad = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e2d45, stop:1 #152238)"
            border = "#2a4066"
        else:
            grad = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #64748b, stop:1 #475569)"
            border = "#94a3b8"

        self._header.setStyleSheet(f"QFrame {{ background: {grad}; border-bottom: 1px solid {border}; }}")

    def render_timeline(self, data: Dict[str, Any], start: datetime = None, end: datetime = None):
        """Render timeline. Accepts data dict containing either Dicts or ViewModels."""
        if not self._is_compact:
            self._update_header_style()

        self._timeline_data = data

        if not end:
            end = datetime.now()
        if not start:
            start = end - timedelta(hours=24)

        self._time_ruler.set_time_range(start, end, self.LABEL_WIDTH)
        self._time_ruler.update()

        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (code, segs) in enumerate(data.items()):
            row = GanttRowWidget(code, segs, start, end, self.LABEL_WIDTH)
            row.set_row_index(i)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch()

        bg = theme_manager.get_color("chart.bg") if not self._is_compact else "transparent"
        self._content.setStyleSheet(f"background: {bg};")
