from datetime import datetime, timedelta
from typing import List, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPaintEvent, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QRectF

from iFactory.presentation.viewmodels.gantt_viewmodel import GanttBarViewModel


class GanttChart(QWidget):
    """
    Visual component rendering a status timeline.
    Accepts ViewModels for rendering.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars: List[GanttBarViewModel] = []
        self._start_time = datetime.now()
        self._end_time = datetime.now()
        self.setBackgroundRole(self.NoRole)

    def set_data(
        self,
        bars: List[GanttBarViewModel],
        start: datetime,
        end: datetime,
    ):
        self._bars = bars
        self._start_time = start
        self._end_time = end
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw Background
        painter.fillRect(self.rect(), QColor("#f0f0f0"))

        if not self._bars:
            self._draw_placeholder(painter)
            return

        total_duration = (self._end_time - self._start_time).total_seconds()
        if total_duration <= 0:
            return

        width = self.width()
        height = 60  # Fixed height for the bar track
        y_offset = (self.height() - height) / 2

        # Draw Bars
        for bar in self._bars:
            # Calculate position relative to window
            offset_seconds = (bar.start_time - self._start_time).total_seconds()
            bar_width = (bar.duration_seconds / total_duration) * width
            x_pos = (offset_seconds / total_duration) * width

            rect = QRectF(x_pos, y_offset, bar_width, height)

            painter.setBrush(QBrush(QColor(bar.color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)

        # Draw Time Axis Grid (hourly)
        self._draw_grid(painter, width, total_duration)

    def _draw_grid(self, painter: QPainter, width: float, total_duration: float):
        painter.setPen(QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine))

        current = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current < self._start_time:
            current += timedelta(hours=1)

        while current < self._end_time:
            offset = (current - self._start_time).total_seconds()
            x = (offset / total_duration) * width

            painter.drawLine(int(x), 0, int(x), self.height())

            # Time Label
            painter.drawText(int(x) + 2, self.height() - 2, current.strftime("%H:%M"))

            current += timedelta(hours=1)

    def _draw_placeholder(self, painter: QPainter):
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No timeline data available for selected period.")
