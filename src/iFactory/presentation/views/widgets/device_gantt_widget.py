# File: presentation/views/widgets/device_gantt_widget.py
"""
Device Gantt Widget - Optimized for 50px height.

Layout (50px total):
┌────────┬──────────────────────────────────────────────────┐
│ DEVICE │ ████████DATA████████░░░░FUTURE░░░░│              │
│  CODE  │ 0      6      12      18    ▼     24             │
└────────┴──────────────────────────────────────────────────┘

Features:
1. Device label on the left (50px width)
2. Gantt bar with status colors
3. Hour markers (0, 6, 12, 18, 24)
4. Future zone with diagonal stripes
5. Current time indicator (red triangle)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, QRectF, Signal, QTimer, Slot, QPointF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QToolTip,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ...constants.colors import get_color_registry, ColorRegistry
from ...constants.status import Status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


# ============================================================================
# Layout Constants for 50px height
# ============================================================================

WIDGET_HEIGHT = 50
WIDGET_PADDING = 2
DEVICE_LABEL_WIDTH = 50
LABEL_SPACING = 4

# Internal view layout
BAR_TOP = 2
BAR_HEIGHT = 26
RULER_GAP = 1
RULER_HEIGHT = 12

# Hour marker settings
TICK_HEIGHT_MAJOR = 4
TICK_HEIGHT_MINOR = 2
FONT_SIZE_HOUR = 8


# ============================================================================
# Data Classes
# ============================================================================


class PrecomputedGanttSegment:
    """Pre-computed segment data for efficient rendering."""

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


# ============================================================================
# Graphics Items
# ============================================================================


class GanttSegmentItem(QGraphicsRectItem):
    """Colored segment in the Gantt chart with hover tooltip."""

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

        # Apply gradient fill
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
            f"{self._start_time.strftime('%H:%M:%S')} → {self._end_time.strftime('%H:%M:%S')}<br>"
            f"Duration: {duration_str}"
            f"</small>"
        )
        QToolTip.showText(event.screenPos(), tooltip)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        QToolTip.hideText()
        super().hoverLeaveEvent(event)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"


# ============================================================================
# Main Widget
# ============================================================================


class DeviceGanttDisplayWidget(QWidget):
    """
    Compact Gantt chart widget - 50px height.

    Layout:
    ┌────────┬──────────────────────────────────────────────────┐
    │ DEVICE │ ████████DATA████████░░░░FUTURE░░░░│              │
    │  CODE  │ 0      6      12      18    ▼     24             │
    └────────┴──────────────────────────────────────────────────┘
    """

    device_clicked = Signal(str)

    # Loading animation
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

        # Data state
        self._device_code: Optional[str] = None
        self._device_name: str = ""
        self._precomputed_segments: List[PrecomputedGanttSegment] = []
        self._start_time: Optional[datetime] = None  # 00:00 today
        self._end_time: Optional[datetime] = None  # 24:00 today
        self._current_time: Optional[datetime] = None  # Now
        self._total_seconds: float = 86400  # 24 hours

        # UI state
        self._is_loading: bool = False
        self._loading_offset: float = 0
        self._loading_timer: Optional[QTimer] = None
        self._is_visible: bool = True
        self._last_render_id: str = ""

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)

    @property
    def tokens(self):
        return self._theme_service.tokens

    def _setup_ui(self) -> None:
        """Setup compact layout for 50px height."""
        self.setFixedHeight(WIDGET_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(WIDGET_PADDING, WIDGET_PADDING, WIDGET_PADDING, WIDGET_PADDING)
        layout.setSpacing(LABEL_SPACING)

        # Device label (left)
        self._device_label = QLabel("--")
        self._device_label.setFixedSize(DEVICE_LABEL_WIDTH, WIDGET_HEIGHT - WIDGET_PADDING * 2)
        self._device_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._device_label.setObjectName("gantt_device_label")
        layout.addWidget(self._device_label)

        # Gantt chart view (right)
        view_height = WIDGET_HEIGHT - WIDGET_PADDING * 2

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setObjectName("gantt_view")
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setFixedHeight(view_height)
        self._view.setMouseTracking(True)
        self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        layout.addWidget(self._view, 1)

        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()
        if self._device_code:
            self._render_timeline()

    def _apply_theme(self) -> None:
        tokens = self.tokens

        self._device_label.setStyleSheet(
            f"""
            QLabel#gantt_device_label {{
                background-color: {tokens.primary};
                color: {tokens.text_inverse};
                font-size: 11px;
                font-weight: bold;
                font-family: "Consolas", monospace;
                border-radius: {tokens.radius_sm};
            }}
        """
        )

        self._view.setStyleSheet(
            f"""
            QGraphicsView#gantt_view {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_sm};
            }}
        """
        )

    def set_theme(self, is_dark: bool) -> None:
        """Compatibility method."""
        pass

    def _update_label_style(self, bg_color: str) -> None:
        """Update device label with specific background color."""
        tokens = self.tokens
        self._device_label.setStyleSheet(
            f"""
            QLabel#gantt_device_label {{
                background-color: {bg_color};
                color: {tokens.text_inverse};
                font-size: 11px;
                font-weight: bold;
                font-family: "Consolas", monospace;
                border-radius: {tokens.radius_sm};
            }}
        """
        )

    def show_placeholder(self) -> None:
        """Show empty placeholder state."""
        self._stop_loading_animation()
        self._device_code = None
        self._device_label.setText("--")
        self._update_label_style(self.tokens.text_muted)
        self._precomputed_segments.clear()
        self._is_loading = False
        self._last_render_id = ""
        self._scene.clear()

        vp = self._view.viewport()
        view_width = max(vp.width(), 200)
        view_height = vp.height()

        self._scene.setSceneRect(0, 0, view_width, view_height)

        # Placeholder text
        text_color = self._colors.get_color(self.tokens.text_muted)
        font = self._colors.get_font(self.tokens.font_family, 10)
        text = self._scene.addSimpleText("← Select a device", font)
        text.setBrush(QBrush(text_color))
        tr = text.boundingRect()
        text.setPos((view_width - tr.width()) / 2, (view_height - tr.height()) / 2)

    def render_device_gantt(
        self,
        device_code: str,
        device_name: str,
        segments: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        current_time: Optional[datetime] = None,
    ) -> None:
        """
        Render Gantt chart for a device.

        Args:
            device_code: Equipment code (e.g., "CWD01")
            device_name: Display name
            segments: Status segments (historical data only, 00:00 to now)
            start_time: 00:00 of current day
            end_time: 24:00 of current day
            current_time: Current time (for future zone rendering)
        """
        segment_count = len(segments) if segments else 0
        is_loading = "(Loading...)" in device_name

        render_id = f"{device_code}:{segment_count}:{'L' if is_loading else 'D'}"
        if not is_loading and render_id == self._last_render_id:
            return

        if not is_loading:
            logger.info(f"[GanttWidget] render: {device_code}, {segment_count} segments")

        # Update state
        self._last_render_id = render_id
        self._device_code = device_code
        self._device_name = device_name
        self._start_time = start_time
        self._end_time = end_time
        self._current_time = current_time or datetime.now()
        self._total_seconds = (end_time - start_time).total_seconds()
        self._is_loading = is_loading

        # Update device label
        label_text = device_code[:6] if len(device_code) > 6 else device_code
        self._device_label.setText(label_text)

        # Color label based on current status
        current_color = self._get_current_status_color(segments)
        self._update_label_style(current_color)

        # Precompute segments
        self._precompute_segments(segments or [])

        if self._is_loading and not self._precomputed_segments:
            self._start_loading_animation()
        else:
            self._stop_loading_animation()
            self._render_timeline()

    def _get_current_status_color(self, segments: List[Dict[str, Any]]) -> str:
        """Get color for the most recent status."""
        if not segments:
            return self.tokens.text_muted

        now = datetime.now()
        for seg in reversed(segments):
            end_time = seg.get("end_time")
            if end_time and end_time >= now:
                return Status.get_color(int(seg.get("status_code", 0)))

        # Default to last segment's color
        return Status.get_color(int(segments[-1].get("status_code", 0)))

    def _precompute_segments(self, segments: List[Dict[str, Any]]) -> None:
        """Pre-compute segment geometry for rendering."""
        self._precomputed_segments.clear()

        if not segments or not self._start_time:
            return

        vp = self._view.viewport()
        view_width = max(vp.width() - 2, 200)
        clip_end = self._current_time or datetime.now()

        for seg in segments:
            start = seg.get("start_time")
            end = seg.get("end_time")

            if not start or not end:
                continue

            # Parse datetime if string
            if isinstance(start, str):
                try:
                    start = datetime.fromisoformat(start.replace("Z", ""))
                except:
                    continue
            if isinstance(end, str):
                try:
                    end = datetime.fromisoformat(end.replace("Z", ""))
                except:
                    continue

            # Clip to valid range (start_time to current_time)
            clipped_start = max(start, self._start_time)
            clipped_end = min(end, clip_end)

            if clipped_start >= clipped_end:
                continue

            # Calculate geometry
            start_offset = (clipped_start - self._start_time).total_seconds()
            duration = (clipped_end - clipped_start).total_seconds()

            x = (start_offset / self._total_seconds) * view_width
            w = max((duration / self._total_seconds) * view_width, 2)

            status_code = int(seg.get("status_code", 0))
            status_name = seg.get("status_name") or Status.get_name(status_code)

            self._precomputed_segments.append(
                PrecomputedGanttSegment(
                    x=x,
                    width=w,
                    status_code=status_code,
                    status_name=status_name,
                    start_time=clipped_start,
                    end_time=clipped_end,
                    duration_seconds=duration,
                )
            )

    def _render_timeline(self) -> None:
        """Render the complete timeline."""
        self._scene.clear()

        if not self._device_code or not self._start_time:
            self.show_placeholder()
            return

        vp = self._view.viewport()
        view_width = max(vp.width() - 2, 200)
        view_height = vp.height()

        self._scene.setSceneRect(0, 0, view_width, view_height)

        tokens = self.tokens

        # Background
        bg = self._colors.get_color(tokens.surface_card)
        self._scene.addRect(QRectF(0, 0, view_width, view_height), QPen(Qt.PenStyle.NoPen), QBrush(bg))

        # Calculate positions based on actual viewport
        bar_y = BAR_TOP
        bar_h = BAR_HEIGHT
        ruler_y = bar_y + bar_h + RULER_GAP

        # 1. Track background
        track_color = self._colors.get_color(tokens.interactive_hover)
        self._scene.addRect(QRectF(0, bar_y, view_width, bar_h), QPen(Qt.PenStyle.NoPen), QBrush(track_color))

        # 2. Segments
        if self._precomputed_segments:
            for seg in self._precomputed_segments:
                if 0 <= seg.x <= view_width:
                    rect = QRectF(seg.x, bar_y, seg.width, bar_h)
                    item = GanttSegmentItem(rect, seg.status_code, seg.status_name, seg.start_time, seg.end_time, seg.duration_seconds)
                    self._scene.addItem(item)
        elif self._is_loading:
            self._render_loading_bar(view_width, bar_h, bar_y)

        # 3. Future zone (now to 24:00)
        self._render_future_zone(view_width, bar_h, bar_y)

        # 4. Hour markers with labels
        self._render_hour_markers(view_width, ruler_y)

        # 5. Current time indicator
        self._render_now_indicator(view_width, bar_y, bar_h)

    def _render_future_zone(self, view_width: float, bar_h: float, bar_y: float) -> None:
        """Render future zone with diagonal stripes."""
        if not self._current_time or not self._start_time:
            return

        now_offset = (self._current_time - self._start_time).total_seconds()
        future_x = (now_offset / self._total_seconds) * view_width
        future_w = view_width - future_x

        if future_w <= 0:
            return

        future_color = self._colors.get_color(self.tokens.border_default)
        future_color.setAlpha(80)

        stripe_brush = QBrush(future_color, Qt.BrushStyle.BDiagPattern)
        self._scene.addRect(QRectF(future_x, bar_y, future_w, bar_h), QPen(Qt.PenStyle.NoPen), stripe_brush)

    def _render_hour_markers(self, view_width: float, ruler_y: float) -> None:
        """Render hour markers with varying tick heights and selective labels."""
        if not self._start_time:
            return

        tokens = self.tokens
        tick_pen = QPen(self._colors.get_color(tokens.text_muted), 1)
        text_color = self._colors.get_color(tokens.text_primary)
        font = self._colors.get_font("Consolas", FONT_SIZE_HOUR)

        # Hours that show labels: 0, 6, 12, 18, 24
        label_hours = {0, 6, 12, 18, 24}
        # Hours with long ticks: 0, 3, 6, 9, 12, 15, 18, 21, 24
        major_tick_hours = {0, 3, 6, 9, 12, 15, 18, 21, 24}

        for hour in range(25):  # 0 to 24 inclusive
            # Calculate x position
            x = (hour * 3600 / self._total_seconds) * view_width

            # Determine tick height
            if hour in major_tick_hours:
                tick_height = TICK_HEIGHT_MAJOR
            else:
                tick_height = TICK_HEIGHT_MINOR

            # Draw tick
            self._scene.addLine(x, ruler_y, x, ruler_y + tick_height, tick_pen)

            # Draw label only for 0, 6, 12, 18, 24
            if hour in label_hours:
                label = str(hour)
                text_item = self._scene.addSimpleText(label, font)
                text_item.setBrush(QBrush(text_color))

                text_rect = text_item.boundingRect()
                text_w = text_rect.width()

                # Position label centered, clamped to bounds
                label_x = x - text_w / 2
                if hour == 0:
                    label_x = max(1, label_x)
                elif hour == 24:
                    label_x = min(view_width - text_w - 1, label_x)

                text_item.setPos(label_x, ruler_y + TICK_HEIGHT_MAJOR + 1)

    def _render_now_indicator(self, view_width: float, bar_y: float, bar_h: float) -> None:
        """Render current time indicator (red line with triangle)."""
        if not self._current_time or not self._start_time or not self._end_time:
            return

        if not (self._start_time <= self._current_time <= self._end_time):
            return

        now_offset = (self._current_time - self._start_time).total_seconds()
        x = (now_offset / self._total_seconds) * view_width

        error_color = self._colors.get_color(self.tokens.error)

        # Vertical line
        self._scene.addLine(x, bar_y, x, bar_y + bar_h, QPen(error_color, 2))

        # Triangle at bottom pointing up
        triangle = QPolygonF(
            [
                QPointF(x - 4, bar_y + bar_h),
                QPointF(x + 4, bar_y + bar_h),
                QPointF(x, bar_y + bar_h - 6),
            ]
        )
        tri = self._scene.addPolygon(triangle, QPen(Qt.PenStyle.NoPen), QBrush(error_color))
        tri.setToolTip(f"Now: {self._current_time.strftime('%H:%M')}")

    def _render_loading_bar(self, view_width: float, bar_h: float, bar_y: float) -> None:
        """Loading shimmer animation."""
        tokens = self.tokens
        gradient = QLinearGradient(0, 0, view_width, 0)

        pos = self._loading_offset
        base = self._colors.get_color(tokens.border_default)
        highlight = self._colors.get_color(tokens.border_strong)

        gradient.setColorAt(0, base)
        gradient.setColorAt(max(0, pos - 0.2), base)
        gradient.setColorAt(min(1, pos), highlight)
        gradient.setColorAt(min(1, pos + 0.2), base)
        gradient.setColorAt(1, base)

        self._scene.addRect(QRectF(0, bar_y, view_width, bar_h), QPen(Qt.PenStyle.NoPen), QBrush(gradient))

        text_color = self._colors.get_color(tokens.text_muted)
        font = self._colors.get_font(tokens.font_family, 9)
        text = self._scene.addSimpleText("Loading...", font)
        text.setBrush(QBrush(text_color))
        tr = text.boundingRect()
        text.setPos((view_width - tr.width()) / 2, bar_y + (bar_h - tr.height()) / 2)

    # ========================================================================
    # Animation
    # ========================================================================

    def _start_loading_animation(self) -> None:
        if not self._is_visible:
            return
        if self._loading_timer is None:
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading)
        self._loading_offset = 0
        self._loading_timer.start(self.LOADING_INTERVAL_MS)
        self._render_timeline()

    def _stop_loading_animation(self) -> None:
        if self._loading_timer:
            self._loading_timer.stop()

    def _update_loading(self) -> None:
        if not self._is_visible:
            self._stop_loading_animation()
            return
        self._loading_offset = (self._loading_offset + 0.04) % 1.0
        if self._is_loading:
            self._render_timeline()

    # ========================================================================
    # Events
    # ========================================================================

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._device_code:
            self._recompute_geometry()
            self._render_timeline()
        else:
            self.show_placeholder()

    def _recompute_geometry(self) -> None:
        """Recompute segment positions on resize."""
        if not self._total_seconds or not self._precomputed_segments:
            return

        vp = self._view.viewport()
        view_width = max(vp.width() - 2, 200)

        for seg in self._precomputed_segments:
            start_offset = (seg.start_time - self._start_time).total_seconds()
            seg.x = (start_offset / self._total_seconds) * view_width
            seg.width = max((seg.duration_seconds / self._total_seconds) * view_width, 2)

    def hideEvent(self, event) -> None:
        self._is_visible = False
        self._stop_loading_animation()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        self._is_visible = True
        super().showEvent(event)
        if self._is_loading:
            self._start_loading_animation()


__all__ = ["DeviceGanttDisplayWidget", "GanttSegmentItem", "PrecomputedGanttSegment"]
