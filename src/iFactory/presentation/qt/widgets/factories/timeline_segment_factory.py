"""
Timeline Segment Factory - Quản lý biểu đồ Gantt.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_GanttStrip = None
_HAS_GANTT = False
try:
    from iFactory.presentation.managers.widgets.gantt.strip import GanttStrip

    _GanttStrip = GanttStrip
    _HAS_GANTT = True
except ImportError:
    _HAS_GANTT = False


class TimelineSegmentFactory(QObject):
    segment_clicked = Signal(str, object)
    data_loaded = Signal(str, int)

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self._frames = {}
        self._theme = "light"

    def set_theme(self, theme: str) -> None:
        """Sửa lỗi 'dict' object has no attribute 'widget'."""
        self._theme = "dark" if theme == "dark" else "light"
        for metadata in self._frames.values():
            # metadata là dictionary nên dùng .get()
            widget = metadata.get("widget")
            if widget and hasattr(widget, "set_theme"):
                try:
                    widget.set_theme(self._theme)
                except RuntimeError:
                    pass

    def register_frame(self, name: str, frame: QFrame) -> Any:
        if not _HAS_GANTT or not frame:
            return None
        if frame.layout():
            QWidget().setLayout(frame.layout())
        try:
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            gantt = _GanttStrip(frame)
            gantt.set_theme(self._theme)
            gantt.segmentClicked.connect(lambda seg: self.segment_clicked.emit(name, seg))
            layout.addWidget(gantt)
            self._frames[name] = {"widget": gantt, "device": ""}
            return gantt
        except Exception as e:
            logger.error(f"Failed to register frame {name}: {e}")
            return None

    def set_data(self, frame_name, device_code, segments, start=None, end=None):
        """4. FIX: Đảm bảo dữ liệu segments luôn là list of tuples hợp lệ."""
        if frame_name in self._frames:
            metadata = self._frames[frame_name]
            widget = metadata["widget"]

            # Chuẩn hóa data: widget Gantt cần (datetime_start, datetime_end, label)
            valid_segments = []
            for s in segments:
                if isinstance(s, (list, tuple)) and len(s) >= 3:
                    valid_segments.append(s)

            try:
                # Ép widget vẽ lại ngay lập tức
                widget.set_data(valid_segments, start, end)
                widget.set_title(f"Lịch sử: {device_code}")
                widget.repaint()
                return True
            except Exception as e:
                logger.error(f"Gantt drawing error: {e}")
        return False


def create_gantt_manager(db=None, **kwargs) -> TimelineSegmentFactory:
    return TimelineSegmentFactory(db=db)
