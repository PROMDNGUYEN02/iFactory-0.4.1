# File: ui/widgets/legend_widget.py
"""
Status Legend Widget - Interactive status legend display with Summary stats.
"""
from __future__ import annotations
import logging
from typing import List, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from iFactory.infrastructure.legend.status_registry import StatusRegistry
from iFactory.application.dtos.gantt_dto import GanttSegmentDto

logger = logging.getLogger(__name__)


class StatusLegendWidget(QFrame):
    """
    Widget hiển thị Legend màu sắc kèm theo thống kê thời gian (Summary).
    """

    def __init__(self, status_registry: StatusRegistry, parent=None):
        super().__init__(parent)
        self._registry = status_registry
        self._current_segments: List[GanttSegmentDto] = []
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("statusLegendWidget")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(15)
        self._placeholder = QLabel("Loading stats...")
        self._placeholder.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._placeholder)
        layout.addStretch()

    def set_gantt_data(self, segments: List[GanttSegmentDto]):
        """
        Cập nhật legend với dữ liệu từ Gantt chart để tính toán % thời gian.
        """
        self._current_segments = segments
        self._update_summary()

    def _update_summary(self):
        """Tính toán tổng thời gian và cập nhật UI."""
        while self.count():
            item = self.takeAt(0)
            if item.widget() and item.widget() != self._placeholder:
                item.widget().deleteLater()
        if not self._current_segments:
            self._placeholder.setText("No data for today")
            self.layout().addWidget(self._placeholder)
            return
        self._placeholder.setVisible(False)
        stats: Dict[int, float] = {}
        total_duration = 0.0
        for seg in self._current_segments:
            duration = seg.duration.total_seconds()
            stats[seg.status_code] = stats.get(seg.status_code, 0.0) + duration
            total_duration += duration
        all_statuses = self._registry.get_all_statuses()
        for status in all_statuses:
            duration = stats.get(status.code, 0.0)
            if duration > 0:
                percent = duration / total_duration * 100 if total_duration > 0 else 0.0
                item_container = QWidget()
                h_item = QHBoxLayout(item_container)
                h_item.setContentsMargins(0, 0, 0, 0)
                h_item.setSpacing(5)
                color_lbl = QLabel()
                color_lbl.setFixedSize(10, 10)
                color_lbl.setStyleSheet(f"background-color: {status.color}; border-radius:2px;")
                text = f"{status.name} {percent:.0f}%"
                text_lbl = QLabel(text)
                text_lbl.setStyleSheet(f"color: {status.color}; font-size: 11px; font-weight: bold;")
                text_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
                h_item.addWidget(color_lbl)
                h_item.addWidget(text_lbl)
                self.layout().addWidget(item_container)


__all__ = ["StatusLegendWidget"]
