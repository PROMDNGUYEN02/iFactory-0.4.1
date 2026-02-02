# File: presentation/views/widgets/device_gantt_widget.py
"""
Optimized Device Gantt Widget - Reduced animation overhead.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QRectF, Signal, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


STATUS_CONFIG = {
    0: {"name": "Unknown", "color": "Transparent", "gradient": ("Transparent", "Transparent")},
    1: {"name": "Running", "color": "#10B981", "gradient": ("#34D399", "#059669")},
    2: {"name": "Shutdown", "color": "#64748B", "gradient": ("#94A3B8", "#64748B")},
    3: {"name": "Stopped", "color": "#EF4444", "gradient": ("#F87171", "#DC2626")},
    4: {"name": "Maintenance", "color": "#8B5CF6", "gradient": ("#A78BFA", "#7C3AED")},
    5: {"name": "Alarm", "color": "#F59E0B", "gradient": ("#FBBF24", "#D97706")},
}


class GanttSegmentItem(QGraphicsRectItem):
    """Interactive segment item with hover tooltip."""

    def __init__(
        self,
        rect: QRectF,
        status_code: int,
        status_name: str,
        start_time: datetime,
        end_time: datetime,
        duration_seconds: float,
        parent=None,
    ):
        super().__init__(rect, parent)
        self._status_code = status_code
        self._status_name = status_name
        self._start_time = start_time
        self._end_time = end_time
        self._duration = duration_seconds

        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        config = STATUS_CONFIG.get(status_code, STATUS_CONFIG[0])
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, QColor(config["gradient"][0]))
        gradient.setColorAt(1, QColor(config["gradient"][1]))
        self.setBrush(QBrush(gradient))
        self.setPen(QPen(Qt.PenStyle.NoPen))

    def hoverEnterEvent(self, event):
        duration_str = self._format_duration(self._duration)
        config = STATUS_CONFIG.get(self._status_code, STATUS_CONFIG[0])
        tooltip = (
            f"<b style='color:{config['color']}'>{self._status_name}</b><br>"
            f"<small>"
            f"Start: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}<br>"
            f"End: {self._end_time.strftime('%Y-%m-%d %H:%M:%S')}<br>"
            f"Duration: {duration_str}"
            f"</small>"
        )
        QToolTip.showText(event.screenPos(), tooltip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"


class DeviceGanttDisplayWidget(QWidget):
    """
    Optimized Gantt widget.

    Changes:
    - Reduced animation FPS (10 FPS instead of 20)
    - Stop animation when not visible
    - Batch scene updates
    """

    device_clicked = Signal(str)

    # Animation settings
    LOADING_FPS = 10  # Reduced from 20
    LOADING_INTERVAL_MS = 1000 // LOADING_FPS

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._device_code: Optional[str] = None
        self._device_name: str = ""
        self._segments: List[Dict[str, Any]] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._is_dark_theme: bool = False
        self._is_loading: bool = False
        self._rendered_count: int = 0

        # Loading animation
        self._loading_offset: float = 0
        self._loading_timer: Optional[QTimer] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setObjectName("gantt_timeline_view")
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setMinimumHeight(20)
        self._view.setMaximumHeight(40)
        self._view.setMouseTracking(True)

        # Optimize rendering
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self._view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        layout.addWidget(self._view)
        self._apply_theme()

    def _apply_theme(self) -> None:
        if self._is_dark_theme:
            view_bg = "#1E293B"
            border = "#334155"
        else:
            view_bg = "#F1F5F9"
            border = "#E2E8F0"

        self._view.setStyleSheet(
            f"""
            QGraphicsView#gantt_timeline_view {{
                background-color: {view_bg};
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """
        )

    def set_theme(self, is_dark: bool) -> None:
        if is_dark != self._is_dark_theme:
            self._is_dark_theme = is_dark
            self._apply_theme()
            if self._device_code and self._segments:
                self._render_timeline()

    def show_placeholder(self) -> None:
        self._stop_loading_animation()
        self._device_code = None
        self._segments = []
        self._is_loading = False
        self._rendered_count = 0
        self._scene.clear()

        view_width = max(self._view.viewport().width(), 200)
        view_height = max(self._view.viewport().height(), 20)
        self._scene.setSceneRect(0, 0, view_width, view_height)

        text_color = QColor("#64748B")
        font = QFont("Segoe UI", 9)
        text_item = self._scene.addSimpleText("Click device to view timeline", font)
        text_item.setBrush(QBrush(text_color))
        text_rect = text_item.boundingRect()
        text_item.setPos((view_width - text_rect.width()) / 2, (view_height - text_rect.height()) / 2)

    def render_device_gantt(
        self,
        device_code: str,
        device_name: str,
        segments: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        logger.info(f"[GanttWidget] render: {device_code}, {len(segments)} segments")

        self._device_code = device_code
        self._device_name = device_name
        self._segments = segments or []
        self._start_time = start_time
        self._end_time = end_time
        self._is_loading = "(Loading...)" in device_name

        if self._is_loading and not self._segments:
            self._start_loading_animation()
        else:
            self._stop_loading_animation()
            self._render_timeline()

    def _start_loading_animation(self) -> None:
        """Start loading shimmer animation (optimized FPS)."""
        if self._loading_timer is None:
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading_animation)

        self._loading_offset = 0
        self._loading_timer.start(self.LOADING_INTERVAL_MS)

        # Render initial loading state
        self._render_timeline()

    def _stop_loading_animation(self) -> None:
        """Stop loading animation."""
        if self._loading_timer:
            self._loading_timer.stop()

    def _update_loading_animation(self) -> None:
        """Update loading animation frame."""
        if not self.isVisible():
            return  # Skip if not visible

        self._loading_offset = (self._loading_offset + 0.05) % 1.0
        if self._is_loading and not self._segments:
            self._render_loading_only()

    def _render_loading_only(self) -> None:
        """Render only loading bar (optimized for animation)."""
        view_width = self._view.viewport().width() - 2
        view_height = self._view.viewport().height() - 2

        if view_width < 50:
            view_width = 400
        if view_height < 10:
            view_height = 30

        # Clear and re-render loading bar only
        self._scene.clear()
        self._scene.setSceneRect(0, 0, view_width, view_height)

        bar_height = view_height - 2
        bar_y = 1

        self._render_loading_bar(view_width, bar_height, bar_y)

    def _render_timeline(self) -> None:
        self._scene.clear()
        self._rendered_count = 0

        if not self._device_code or not self._start_time or not self._end_time:
            self.show_placeholder()
            return

        view_width = self._view.viewport().width() - 2
        view_height = self._view.viewport().height() - 2

        if view_width < 50:
            view_width = 400
        if view_height < 10:
            view_height = 30

        total_seconds = (self._end_time - self._start_time).total_seconds()
        if total_seconds <= 0:
            return

        self._scene.setSceneRect(0, 0, view_width, view_height)

        # Background
        bg_color = QColor("#1E293B" if self._is_dark_theme else "#F8FAFC")
        self._scene.addRect(
            QRectF(0, 0, view_width, view_height),
            QPen(Qt.PenStyle.NoPen),
            QBrush(bg_color),
        )

        bar_height = view_height - 2
        bar_y = 1

        if self._segments:
            for segment in self._segments:
                self._render_segment(segment, view_width, bar_height, bar_y, total_seconds)
            logger.info(f"[GanttWidget] Rendered {self._rendered_count} segments")
        elif self._is_loading:
            self._render_loading_bar(view_width, bar_height, bar_y)
        else:
            self._render_no_data_bar(view_width, bar_height, bar_y)

        self._render_hour_markers(view_width, view_height, total_seconds)
        self._render_current_time_indicator(view_width, view_height, total_seconds)

    def _render_loading_bar(self, view_width: float, bar_height: float, bar_y: float) -> None:
        """Render animated loading state bar."""
        gradient = QLinearGradient(0, 0, view_width, 0)

        shimmer_pos = self._loading_offset
        shimmer_width = 0.3

        if self._is_dark_theme:
            base_color = QColor("#334155")
            highlight_color = QColor("#475569")
        else:
            base_color = QColor("#E2E8F0")
            highlight_color = QColor("#CBD5E1")

        gradient.setColorAt(0, base_color)
        if shimmer_pos > shimmer_width:
            gradient.setColorAt(max(0, shimmer_pos - shimmer_width), base_color)
        gradient.setColorAt(shimmer_pos, highlight_color)
        if shimmer_pos + shimmer_width < 1:
            gradient.setColorAt(min(1, shimmer_pos + shimmer_width), base_color)
        gradient.setColorAt(1, base_color)

        loading_rect = QRectF(0, bar_y, view_width, bar_height)
        self._scene.addRect(loading_rect, QPen(Qt.PenStyle.NoPen), QBrush(gradient))

        text_color = QColor("#94A3B8")
        font = QFont("Segoe UI", 8)
        text_item = self._scene.addSimpleText("Loading timeline...", font)
        text_item.setBrush(QBrush(text_color))
        text_rect = text_item.boundingRect()
        text_item.setPos((view_width - text_rect.width()) / 2, bar_y + (bar_height - text_rect.height()) / 2)

    def _render_no_data_bar(self, view_width: float, bar_height: float, bar_y: float) -> None:
        """Render no-data state bar."""
        no_data_rect = QRectF(0, bar_y, view_width, bar_height)
        no_data_item = self._scene.addRect(
            no_data_rect,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor("#475569" if self._is_dark_theme else "#CBD5E1")),
        )
        no_data_item.setToolTip(f"<b>{self._device_name}</b><br>" f"<small>No history data available for the last 24 hours.</small>")

    def _render_segment(
        self,
        segment: Dict[str, Any],
        view_width: float,
        bar_height: float,
        bar_y: float,
        total_seconds: float,
    ) -> None:
        start = segment.get("start_time")
        end = segment.get("end_time")
        status_code = segment.get("status_code", 0)
        status_name = segment.get("status_name") or STATUS_CONFIG.get(int(status_code), {}).get("name", "Unknown")

        if not start or not end:
            return

        # Parse datetime if string
        if isinstance(start, str):
            try:
                start = datetime.fromisoformat(start.replace("Z", "").replace("+00:00", ""))
            except ValueError:
                return
        if isinstance(end, str):
            try:
                end = datetime.fromisoformat(end.replace("Z", "").replace("+00:00", ""))
            except ValueError:
                return

        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return

        # Clip to window
        clipped_start = max(start, self._start_time)
        clipped_end = min(end, self._end_time)

        if clipped_start >= clipped_end:
            return

        start_offset = (clipped_start - self._start_time).total_seconds()
        duration = (clipped_end - clipped_start).total_seconds()

        x = (start_offset / total_seconds) * view_width
        w = max((duration / total_seconds) * view_width, 2)

        rect = QRectF(x, bar_y, w, bar_height)
        segment_item = GanttSegmentItem(
            rect=rect,
            status_code=int(status_code),
            status_name=status_name,
            start_time=clipped_start,
            end_time=clipped_end,
            duration_seconds=duration,
        )
        self._scene.addItem(segment_item)
        self._rendered_count += 1

    def _render_hour_markers(
        self,
        view_width: float,
        view_height: float,
        total_seconds: float,
    ) -> None:
        if not self._start_time or not self._end_time:
            return

        marker_color = QColor("#475569" if self._is_dark_theme else "#CBD5E1")
        marker_color.setAlpha(80)

        current = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current < self._start_time:
            current += timedelta(hours=1)

        while current <= self._end_time:
            offset = (current - self._start_time).total_seconds()
            x = (offset / total_seconds) * view_width

            pen = QPen(marker_color)
            pen.setWidth(1)
            self._scene.addLine(x, 0, x, view_height * 0.25, pen)

            current += timedelta(hours=1)

    def _render_current_time_indicator(
        self,
        view_width: float,
        view_height: float,
        total_seconds: float,
    ) -> None:
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return

        if self._start_time <= now <= self._end_time:
            offset = (now - self._start_time).total_seconds()
            x = (offset / total_seconds) * view_width

            pen = QPen(QColor("#EF4444"))
            pen.setWidth(2)
            line = self._scene.addLine(x, 0, x, view_height, pen)
            line.setToolTip(f"Now: {now.strftime('%H:%M:%S')}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._device_code and self._segments:
            self._render_timeline()
        elif not self._device_code:
            self.show_placeholder()

    def hideEvent(self, event) -> None:
        """Stop animation when hidden."""
        self._stop_loading_animation()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        """Resume animation if needed when shown."""
        super().showEvent(event)
        if self._is_loading and not self._segments:
            self._start_loading_animation()


__all__ = ["DeviceGanttDisplayWidget"]
