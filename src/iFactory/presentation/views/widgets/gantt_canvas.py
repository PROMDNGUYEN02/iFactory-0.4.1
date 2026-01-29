"""
Professional Gantt Chart Canvas Widget.
Displays device status timeline for 24 hours with clear colors.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QLinearGradient, QPainterPath
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QScrollArea, QFrame

from ...resources.themes.theme_manager import theme_manager
from ...constants.ui_constants import StatusColors

logger = logging.getLogger(__name__)


class GanttRowWidget(QWidget):
    ROW_HEIGHT = 32

    def __init__(self, equip_code: str, segments: List[Dict[str, Any]], start_time: datetime, end_time: datetime, label_width: int = 90, parent=None):
        super().__init__(parent)
        self._equip_code = equip_code
        self._segments = segments
        self._start_time = start_time
        self._end_time = end_time
        self._label_width = label_width
        self._row_index = 0
        self.setFixedHeight(self.ROW_HEIGHT)
        self.setMouseTracking(True)

    def set_row_index(self, index: int):
        self._row_index = index

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # [THEME] Dynamic background
        bg_base = theme_manager.get_qcolor("chart.bg")
        if self._row_index % 2 == 0:
            bg_color = bg_base.lighter(105) if theme_manager.is_dark else bg_base.darker(105)
        else:
            bg_color = bg_base
        painter.fillRect(rect, bg_color)

        # Grid line
        painter.setPen(QPen(theme_manager.get_qcolor("chart.grid"), 1))
        painter.drawLine(self._label_width, rect.height() - 1, rect.width(), rect.height() - 1)

        # Label
        painter.setPen(theme_manager.get_qcolor("chart.text"))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        label_rect = QRectF(5, 0, self._label_width - 10, rect.height())
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._equip_code)

        # Draw segments
        chart_width = rect.width() - self._label_width - 10
        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds > 0:
            for seg in self._segments:
                self._draw_segment(painter, seg, chart_width, total_seconds, 3, rect.height() - 6)

    def _draw_segment(self, painter, seg, chart_width, total_seconds, y, height):
        seg_start = seg.get("start_time")
        seg_end = seg.get("end_time")
        if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
            return

        start_offset = max(0, (seg_start - self._start_time).total_seconds())
        end_offset = min(total_seconds, (seg_end - self._start_time).total_seconds())
        if end_offset <= start_offset:
            return

        x = self._label_width + (start_offset / total_seconds) * chart_width
        width = max(((end_offset - start_offset) / total_seconds) * chart_width, 3)

        status_code = int(seg.get("status_code", 0))
        base_color = QColor(StatusColors.get_color(status_code))  # Theme handled by StatusColors

        rect = QRectF(x, y, width, height)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, base_color.lighter(120))
        gradient.setColorAt(1, base_color)

        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        painter.fillPath(path, QBrush(gradient))
        painter.setPen(QPen(base_color.darker(120), 1))
        painter.drawPath(path)


class TimeRulerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._end_time = self._start_time + timedelta(hours=24)
        self._label_width = 90
        self.setFixedHeight(28)

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

        painter.setFont(QFont("Consolas", 8))
        grid_color = theme_manager.get_qcolor("chart.grid")
        text_color = theme_manager.get_qcolor("chart.text")
        chart_width = rect.width() - self._label_width - 10

        for hour in range(0, 25, 2):
            x = self._label_width + (hour * 3600 / total_seconds) * chart_width
            painter.setPen(QPen(grid_color, 1))
            painter.drawLine(int(x), rect.height() - 6, int(x), rect.height())
            painter.setPen(text_color)
            painter.drawText(int(x) - 18, 2, 36, 18, Qt.AlignCenter, f"{hour:02d}:00")


class GanttCanvasWidget(QWidget):
    segment_clicked = Signal(str, dict)
    LABEL_WIDTH = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline_data = {}
        self._rows = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header (Gradient hardcoded for style, or move to theme)
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e2d45, stop:1 #152238); border-bottom: 1px solid #2a4066; }"
        )
        h_layout = QHBoxLayout(header)
        title = QLabel("📊 Production Timeline (24h)")
        title.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        # Legend
        for code in [1, 3, 4, 5, 0]:
            l = QLabel(f"■ {StatusColors.get_name(code)}")
            l.setStyleSheet(f"color: {StatusColors.get_color(code)}; margin-left: 8px;")
            h_layout.addWidget(l)
        layout.addWidget(header)

        self._time_ruler = TimeRulerWidget()
        layout.addWidget(self._time_ruler)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

    def render_timeline(self, data, start=None, end=None):
        self._timeline_data = data
        start = start or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = end or (start + timedelta(hours=24))
        self._time_ruler.set_time_range(start, end, self.LABEL_WIDTH)

        # Clear rows
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (code, segs) in enumerate(data.items()):
            row = GanttRowWidget(code, segs, start, end, self.LABEL_WIDTH)
            row.set_row_index(i)
            self._content_layout.addWidget(row)
        self._content_layout.addStretch()

        # Update bg color from theme
        self._content.setStyleSheet(f"background: {theme_manager.get_color('chart.bg')};")


__all__ = ["GanttCanvasWidget"]
