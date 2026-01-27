"""
Gantt Chart Canvas Widget.
Displays device status timeline with interactive segments.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class GanttSegmentItem(QGraphicsRectItem):
    """Interactive segment with tooltip."""

    def __init__(self, x: float, y: float, w: float, h: float, segment_data: Dict[str, Any]):
        super().__init__(x, y, w, h)
        self.setBrush(QBrush(QColor(segment_data.get("color", "#888888"))))
        self.setPen(QPen(Qt.NoPen))
        self.setAcceptHoverEvents(True)
        self.data = segment_data

    def hoverEnterEvent(self, event) -> None:
        self.setOpacity(0.8)
        tooltip = f"""
        <div style='background:#2c3e50; color:white; padding:5px; border-radius:4px;'>
            <b>Status:</b> {self.data.get('status_name', 'Unknown')}<br>
            <b>Start:</b> {self.data.get('start_time', 'N/A')}<br>
            <b>End:</b> {self.data.get('end_time', 'N/A')}
        </div>
        """
        QToolTip.showText(QCursor.pos(), tooltip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setOpacity(1.0)
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


class GanttCanvasWidget(QWidget):
    """Gantt chart visualization widget."""

    ROW_HEIGHT = 40
    LABEL_WIDTH = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        layout.addWidget(self.view)

    def render_timeline(self, timeline_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Render timeline from ViewModel data."""
        self.scene.clear()

        view_rect = self.view.viewport().rect()
        chart_w = max(view_rect.width() - self.LABEL_WIDTH - 20, 800)
        y_pos = 40

        self._draw_time_ruler(chart_w, y_pos, len(timeline_data))

        for equip_code, segments in timeline_data.items():
            self._draw_device_row(equip_code, segments, y_pos, chart_w)
            y_pos += self.ROW_HEIGHT

        self._draw_current_time_indicator(chart_w, y_pos)
        self.scene.setSceneRect(0, 0, chart_w + self.LABEL_WIDTH, y_pos + 20)

    def _draw_time_ruler(self, chart_w: float, y_start: float, row_count: int) -> None:
        grid_pen = QPen(QColor("#404040"), 1, Qt.DotLine)
        for hour in range(0, 25, 2):
            x = self.LABEL_WIDTH + (hour / 24.0) * chart_w
            self.scene.addLine(x, y_start, x, y_start + row_count * self.ROW_HEIGHT, grid_pen)

            time_lbl = self.scene.addText(f"{hour:02d}:00")
            time_lbl.setDefaultTextColor(QColor("#888888"))
            time_lbl.setFont(QFont("Arial", 8))
            time_lbl.setPos(x - 15, 15)

    def _draw_device_row(
        self,
        equip_code: str,
        segments: List[Dict[str, Any]],
        y_pos: float,
        chart_w: float,
    ) -> None:
        label = self.scene.addText(equip_code)
        label.setDefaultTextColor(QColor("#cccccc"))
        label.setFont(QFont("Arial", 10, QFont.Bold))
        label.setPos(5, y_pos + 10)

        current_x = self.LABEL_WIDTH
        for seg in segments:
            seg_width = chart_w * seg.get("percent", 0)
            item = GanttSegmentItem(current_x, y_pos + 8, seg_width, self.ROW_HEIGHT - 16, seg)
            self.scene.addItem(item)
            current_x += seg_width

    def _draw_current_time_indicator(self, chart_w: float, y_end: float) -> None:
        now = datetime.now()
        hours_passed = now.hour + now.minute / 60.0
        now_x = self.LABEL_WIDTH + (hours_passed / 24.0) * chart_w

        self.scene.addLine(now_x, 30, now_x, y_end, QPen(QColor("#e74c3c"), 2))

        now_lbl = self.scene.addText("NOW")
        now_lbl.setDefaultTextColor(QColor("#e74c3c"))
        now_lbl.setFont(QFont("Arial", 8, QFont.Bold))
        now_lbl.setPos(now_x - 15, 15)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)


__all__ = ["GanttCanvasWidget"]
