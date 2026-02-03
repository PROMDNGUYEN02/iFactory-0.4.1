# File: presentation/views/widgets/device_gantt_widget.py
"""
Optimized Device Gantt Widget.

Key optimizations:
1. ColorRegistry for cached colors
2. Stop animation when not visible
3. Reduced animation FPS
4. Pre-computed segment geometry
5. Duplicate render prevention (FIXED)
6. Viewport culling for large datasets
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, QRectF, Signal, QTimer, Slot
from PySide6.QtGui import (
    QBrush,
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

from ...constants.colors import get_color_registry, ColorRegistry
from ...constants.status import Status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class PrecomputedGanttSegment:
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


class GanttSegmentItem(QGraphicsRectItem):
    _colors: Optional[ColorRegistry] = None

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

        if GanttSegmentItem._colors is None:
            GanttSegmentItem._colors = get_color_registry()

        start_color, end_color = self._colors.get_status_gradient_colors(status_code)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, start_color)
        gradient.setColorAt(1, end_color)
        self.setBrush(QBrush(gradient))
        self.setPen(QPen(Qt.PenStyle.NoPen))

    def hoverEnterEvent(self, event):
        duration_str = self._format_duration(self._duration)
        color = self._colors.STATUS_COLORS.get(self._status_code, "#9E9E9E")
        tooltip = (
            f"<b style='color:{color}'>{self._status_name}</b><br>"
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
    Widget displaying Gantt chart for a device.

    FIXED: Proper duplicate render prevention using render_id.
    """

    device_clicked = Signal(str)

    LOADING_FPS = 10
    LOADING_INTERVAL_MS = 1000 // LOADING_FPS

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

        self._device_code: Optional[str] = None
        self._device_name: str = ""
        self._precomputed_segments: List[PrecomputedGanttSegment] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._total_seconds: float = 0
        self._is_loading: bool = False
        self._rendered_count: int = 0
        self._cached_view_width: float = 0
        self._cached_view_height: float = 0

        # FIXED: Use a composite render ID for proper duplicate detection
        self._last_render_id: str = ""

        self._loading_offset: float = 0
        self._loading_timer: Optional[QTimer] = None
        self._is_visible: bool = True

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)

    def _generate_render_id(
        self,
        device_code: str,
        segment_count: int,
        is_loading: bool,
    ) -> str:
        """Generate unique render ID for duplicate detection."""
        # Loading states are transient, always allow them but don't log
        if is_loading:
            return f"{device_code}:loading:{id(self)}"

        # For data renders, use device + count
        return f"{device_code}:{segment_count}:data"

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()
        if self._device_code and self._precomputed_segments:
            self._render_timeline()

    @property
    def tokens(self):
        return self._theme_service.tokens

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
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self._view.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        layout.addWidget(self._view)
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self._view.setStyleSheet(
            f"""
            QGraphicsView#gantt_timeline_view {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_sm};
            }}
        """
        )

    def set_theme(self, is_dark: bool) -> None:
        pass

    def show_placeholder(self) -> None:
        self._stop_loading_animation()
        self._device_code = None
        self._precomputed_segments.clear()
        self._is_loading = False
        self._rendered_count = 0
        self._last_render_id = ""
        self._scene.clear()

        view_width = max(self._view.viewport().width(), 200)
        view_height = max(self._view.viewport().height(), 20)
        self._scene.setSceneRect(0, 0, view_width, view_height)

        tokens = self.tokens
        text_color = self._colors.get_color(tokens.text_muted)
        font = self._colors.get_font(tokens.font_family, 9)
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
        """
        Render Gantt chart for device.

        FIXED: Proper duplicate detection with render_id.
        """
        segment_count = len(segments) if segments else 0
        is_loading_state = "(Loading...)" in device_name

        # Generate render ID for duplicate detection
        render_id = self._generate_render_id(device_code, segment_count, is_loading_state)

        # Check for duplicate (skip loading states from duplicate check)
        if not is_loading_state and render_id == self._last_render_id:
            # True duplicate - skip silently
            return

        # Only log for actual data renders, not loading states
        if not is_loading_state:
            logger.info(f"[GanttWidget] render: {device_code}, {segment_count} segments")

        # Update state
        self._last_render_id = render_id
        self._device_code = device_code
        self._device_name = device_name
        self._start_time = start_time
        self._end_time = end_time
        self._total_seconds = max((end_time - start_time).total_seconds(), 1)
        self._is_loading = is_loading_state

        self._precompute_segments(segments or [])

        if self._is_loading and not self._precomputed_segments:
            self._start_loading_animation()
        else:
            self._stop_loading_animation()
            self._render_timeline()

    def _precompute_segments(self, segments: List[Dict[str, Any]]) -> None:
        self._precomputed_segments.clear()

        if not segments or not self._start_time or not self._end_time:
            return

        view_width = max(self._view.viewport().width() - 2, 200)

        for segment in segments:
            start = segment.get("start_time")
            end = segment.get("end_time")
            status_code = segment.get("status_code", 0)
            status_name = segment.get("status_name", "")

            if not start or not end:
                continue

            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start.replace("Z", "").replace("+00:00", ""))
                except ValueError:
                    continue
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end.replace("Z", "").replace("+00:00", ""))
                except ValueError:
                    continue

            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue

            clipped_start = max(start, self._start_time)
            clipped_end = min(end, self._end_time)

            if clipped_start >= clipped_end:
                continue

            start_offset = (clipped_start - self._start_time).total_seconds()
            duration = (clipped_end - clipped_start).total_seconds()

            x = (start_offset / self._total_seconds) * view_width
            w = max((duration / self._total_seconds) * view_width, 2)

            if not status_name:
                status_name = Status.get_name(int(status_code) if status_code else 0)

            self._precomputed_segments.append(
                PrecomputedGanttSegment(
                    x=x,
                    width=w,
                    status_code=int(status_code) if status_code else 0,
                    status_name=status_name,
                    start_time=clipped_start,
                    end_time=clipped_end,
                    duration_seconds=duration,
                )
            )

    def _start_loading_animation(self) -> None:
        if not self._is_visible:
            return

        if self._loading_timer is None:
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading_animation)

        self._loading_offset = 0
        self._loading_timer.start(self.LOADING_INTERVAL_MS)
        self._render_timeline()

    def _stop_loading_animation(self) -> None:
        if self._loading_timer:
            self._loading_timer.stop()

    def _update_loading_animation(self) -> None:
        if not self._is_visible:
            self._stop_loading_animation()
            return

        self._loading_offset = (self._loading_offset + 0.05) % 1.0
        if self._is_loading and not self._precomputed_segments:
            self._render_loading_only()

    def _render_loading_only(self) -> None:
        view_width = self._view.viewport().width() - 2
        view_height = self._view.viewport().height() - 2

        if view_width < 50:
            view_width = 400
        if view_height < 10:
            view_height = 30

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

        self._cached_view_width = view_width
        self._cached_view_height = view_height
        self._scene.setSceneRect(0, 0, view_width, view_height)

        tokens = self.tokens
        bg_color = self._colors.get_color(tokens.surface_card)
        self._scene.addRect(
            QRectF(0, 0, view_width, view_height),
            QPen(Qt.PenStyle.NoPen),
            QBrush(bg_color),
        )

        bar_height = view_height - 2
        bar_y = 1

        if self._precomputed_segments:
            for seg in self._precomputed_segments:
                if seg.x > view_width:
                    continue
                if seg.x + seg.width < 0:
                    continue
                self._render_segment(seg, bar_height, bar_y)
        elif self._is_loading:
            self._render_loading_bar(view_width, bar_height, bar_y)
        else:
            self._render_no_data_bar(view_width, bar_height, bar_y)

        self._render_hour_markers(view_width, view_height)
        self._render_current_time_indicator(view_width, view_height)

    def _render_loading_bar(
        self,
        view_width: float,
        bar_height: float,
        bar_y: float,
    ) -> None:
        tokens = self.tokens
        gradient = QLinearGradient(0, 0, view_width, 0)

        shimmer_pos = self._loading_offset
        shimmer_width = 0.3

        base_color = self._colors.get_color(tokens.border_default)
        highlight_color = self._colors.get_color(tokens.border_strong)

        gradient.setColorAt(0, base_color)
        if shimmer_pos > shimmer_width:
            gradient.setColorAt(max(0, shimmer_pos - shimmer_width), base_color)
        gradient.setColorAt(min(1, shimmer_pos), highlight_color)
        if shimmer_pos + shimmer_width < 1:
            gradient.setColorAt(min(1, shimmer_pos + shimmer_width), base_color)
        gradient.setColorAt(1, base_color)

        loading_rect = QRectF(0, bar_y, view_width, bar_height)
        self._scene.addRect(loading_rect, QPen(Qt.PenStyle.NoPen), QBrush(gradient))

        text_color = self._colors.get_color(tokens.text_muted)
        font = self._colors.get_font(tokens.font_family, 8)
        text_item = self._scene.addSimpleText("Loading timeline...", font)
        text_item.setBrush(QBrush(text_color))
        text_rect = text_item.boundingRect()
        text_item.setPos((view_width - text_rect.width()) / 2, bar_y + (bar_height - text_rect.height()) / 2)

    def _render_no_data_bar(
        self,
        view_width: float,
        bar_height: float,
        bar_y: float,
    ) -> None:
        tokens = self.tokens
        no_data_rect = QRectF(0, bar_y, view_width, bar_height)
        no_data_brush = self._colors.get_brush(tokens.text_muted)
        no_data_item = self._scene.addRect(
            no_data_rect,
            QPen(Qt.PenStyle.NoPen),
            no_data_brush,
        )
        no_data_item.setToolTip(f"<b>{self._device_name}</b><br>" f"<small>No history data available for the last 24 hours.</small>")

    def _render_segment(
        self,
        seg: PrecomputedGanttSegment,
        bar_height: float,
        bar_y: float,
    ) -> None:
        rect = QRectF(seg.x, bar_y, seg.width, bar_height)
        segment_item = GanttSegmentItem(
            rect=rect,
            status_code=seg.status_code,
            status_name=seg.status_name,
            start_time=seg.start_time,
            end_time=seg.end_time,
            duration_seconds=seg.duration_seconds,
        )
        self._scene.addItem(segment_item)
        self._rendered_count += 1

    def _render_hour_markers(
        self,
        view_width: float,
        view_height: float,
    ) -> None:
        if not self._start_time or not self._end_time:
            return

        tokens = self.tokens
        marker_pen = self._colors.get_pen(tokens.border_default, 1)

        current = self._start_time.replace(minute=0, second=0, microsecond=0)
        if current < self._start_time:
            current += timedelta(hours=1)

        while current <= self._end_time:
            offset = (current - self._start_time).total_seconds()
            x = (offset / self._total_seconds) * view_width

            self._scene.addLine(x, 0, x, view_height * 0.25, marker_pen)
            current += timedelta(hours=1)

    def _render_current_time_indicator(
        self,
        view_width: float,
        view_height: float,
    ) -> None:
        now = datetime.now()
        if not self._start_time or not self._end_time:
            return

        if self._start_time <= now <= self._end_time:
            offset = (now - self._start_time).total_seconds()
            x = (offset / self._total_seconds) * view_width

            tokens = self.tokens
            error_pen = self._colors.get_pen(tokens.error, 2)
            line = self._scene.addLine(x, 0, x, view_height, error_pen)
            line.setToolTip(f"Now: {now.strftime('%H:%M:%S')}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._device_code and self._precomputed_segments:
            self._recompute_geometry()
            self._render_timeline()
        elif not self._device_code:
            self.show_placeholder()

    def _recompute_geometry(self) -> None:
        if not self._total_seconds or not self._precomputed_segments:
            return

        view_width = max(self._view.viewport().width() - 2, 200)

        for seg in self._precomputed_segments:
            start_offset = (seg.start_time - self._start_time).total_seconds()
            duration = seg.duration_seconds
            seg.x = (start_offset / self._total_seconds) * view_width
            seg.width = max((duration / self._total_seconds) * view_width, 2)

    def hideEvent(self, event) -> None:
        self._is_visible = False
        self._stop_loading_animation()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        self._is_visible = True
        super().showEvent(event)
        if self._is_loading and not self._precomputed_segments:
            self._start_loading_animation()


__all__ = ["DeviceGanttDisplayWidget", "GanttSegmentItem", "PrecomputedGanttSegment"]
