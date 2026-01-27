"""
Professional Gantt Chart Canvas Widget.
Displays device status timeline for 24 hours with clear colors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
    QLinearGradient,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QScrollArea,
    QFrame,
)

logger = logging.getLogger(__name__)


# Clear, distinct status colors
STATUS_COLORS = {
    "0": {"color": "#9E9E9E", "name": "Unknown", "gradient": ["#BDBDBD", "#9E9E9E"]},
    "1": {"color": "#4CAF50", "name": "Running", "gradient": ["#66BB6A", "#4CAF50"]},
    "2": {"color": "#607D8B", "name": "Shutdown", "gradient": ["#78909C", "#607D8B"]},
    "3": {"color": "#F44336", "name": "Stopped", "gradient": ["#EF5350", "#F44336"]},
    "4": {"color": "#2196F3", "name": "Maintenance", "gradient": ["#42A5F5", "#2196F3"]},
    "5": {"color": "#FF9800", "name": "Alarm", "gradient": ["#FFA726", "#FF9800"]},
}


def get_status_info(status_code) -> Dict[str, Any]:
    return STATUS_COLORS.get(str(status_code), STATUS_COLORS["0"])


class GanttRowWidget(QWidget):
    """Single row representing one device's timeline."""

    ROW_HEIGHT = 32

    def __init__(
        self,
        equip_code: str,
        segments: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        label_width: int = 90,
        parent=None,
    ):
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
        chart_width = rect.width() - self._label_width - 10

        # Alternating row background
        bg_color = QColor("#1a1f2e") if self._row_index % 2 == 0 else QColor("#141820")
        painter.fillRect(rect, bg_color)

        # Grid line
        painter.setPen(QPen(QColor("#2a3040"), 1))
        painter.drawLine(self._label_width, rect.height() - 1, rect.width(), rect.height() - 1)

        # Label
        painter.setPen(QColor("#e0e0e0"))
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        label_rect = QRectF(5, 0, self._label_width - 10, rect.height())
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._equip_code)

        # Draw segments
        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        seg_height = rect.height() - 6
        seg_y = 3

        for seg in self._segments:
            self._draw_segment(painter, seg, chart_width, total_seconds, seg_y, seg_height)

    def _draw_segment(self, painter: QPainter, seg: Dict, chart_width: float, total_seconds: float, y: float, height: float):
        seg_start = seg.get("start_time")
        seg_end = seg.get("end_time")

        if not isinstance(seg_start, datetime) or not isinstance(seg_end, datetime):
            return

        start_offset = max(0, (seg_start - self._start_time).total_seconds())
        end_offset = min(total_seconds, (seg_end - self._start_time).total_seconds())

        if end_offset <= start_offset:
            return

        x = self._label_width + (start_offset / total_seconds) * chart_width
        width = ((end_offset - start_offset) / total_seconds) * chart_width
        width = max(width, 3)

        status_code = str(seg.get("status_code", "0"))
        status_info = get_status_info(status_code)
        colors = [QColor(c) for c in status_info["gradient"]]

        rect = QRectF(x, y, width, height)
        corner = min(4, height / 3)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, colors[0])
        gradient.setColorAt(1, colors[1])

        path = QPainterPath()
        path.addRoundedRect(rect, corner, corner)
        painter.fillPath(path, QBrush(gradient))

        painter.setPen(QPen(colors[1].darker(120), 1))
        painter.drawPath(path)

        if width > 50:
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            text_rect = rect.adjusted(4, 0, -4, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, status_info["name"])


class TimeRulerWidget(QWidget):
    """Time ruler for 24h display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._end_time = self._start_time + timedelta(hours=24)
        self._label_width = 90
        self.setFixedHeight(28)

    def set_time_range(self, start: datetime, end: datetime, label_width: int = 90):
        self._start_time = start
        self._end_time = end
        self._label_width = label_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        chart_width = rect.width() - self._label_width - 10

        painter.fillRect(rect, QColor("#0d1117"))

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        # Hour markers
        painter.setFont(QFont("Consolas", 8))

        for hour in range(0, 25, 2):
            x = self._label_width + (hour * 3600 / total_seconds) * chart_width

            painter.setPen(QPen(QColor("#3d5166"), 1))
            painter.drawLine(int(x), rect.height() - 6, int(x), rect.height())

            painter.setPen(QColor("#8892a0"))
            painter.drawText(int(x) - 18, 2, 36, 18, Qt.AlignCenter, f"{hour:02d}:00")

        # NOW indicator
        now = datetime.now()
        if self._start_time <= now <= self._end_time:
            elapsed = (now - self._start_time).total_seconds()
            now_x = self._label_width + (elapsed / total_seconds) * chart_width

            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(int(now_x), 0, int(now_x), rect.height())

            painter.setPen(QColor("#ef4444"))
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.drawText(int(now_x) - 12, 1, 24, 12, Qt.AlignCenter, "NOW")


class GanttCanvasWidget(QWidget):
    """Professional 24-hour Gantt chart."""

    segment_clicked = Signal(str, dict)
    LABEL_WIDTH = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._end_time = self._start_time + timedelta(hours=24)
        self._timeline_data: Dict[str, List[Dict[str, Any]]] = {}
        self._rows: List[GanttRowWidget] = []

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = self._create_header()
        main_layout.addWidget(header)

        self._time_ruler = TimeRulerWidget()
        main_layout.addWidget(self._time_ruler)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea { border: none; background: #0d1117; }
            QScrollBar:vertical {
                background: #1a1f2e; width: 8px; border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3d4663; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """
        )

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: #0d1117;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        scroll.setWidget(self._content_widget)
        main_layout.addWidget(scroll, 1)

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e2d45, stop:1 #152238);
                border-bottom: 1px solid #2a4066;
            }
        """
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 4, 10, 4)

        title = QLabel("📊 Production Timeline (24h)")
        title.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        for code in ["1", "3", "4", "5", "0"]:
            info = STATUS_COLORS[code]
            legend = self._create_legend_item(info["name"], info["color"])
            layout.addWidget(legend)

        return header

    def _create_legend_item(self, name: str, color: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(3)

        box = QLabel()
        box.setFixedSize(10, 10)
        box.setStyleSheet(f"background: {color}; border-radius: 2px;")
        layout.addWidget(box)

        label = QLabel(name)
        label.setStyleSheet("color: #888; font-size: 9px;")
        layout.addWidget(label)

        return widget

    def render_timeline(
        self,
        timeline_data: Dict[str, List[Dict[str, Any]]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Render 24h timeline."""
        self._timeline_data = timeline_data

        if start_time:
            self._start_time = start_time
        else:
            self._start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if end_time:
            self._end_time = end_time
        else:
            self._end_time = self._start_time + timedelta(hours=24)

        self._time_ruler.set_time_range(self._start_time, self._end_time, self.LABEL_WIDTH)

        # Clear existing rows
        self._rows.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create rows
        for idx, (equip_code, segments) in enumerate(timeline_data.items()):
            row = GanttRowWidget(
                equip_code=equip_code,
                segments=segments,
                start_time=self._start_time,
                end_time=self._end_time,
                label_width=self.LABEL_WIDTH,
            )
            row.set_row_index(idx)
            self._rows.append(row)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch()

    def clear(self):
        self._timeline_data = {}
        self._rows.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


__all__ = ["GanttCanvasWidget", "STATUS_COLORS"]
