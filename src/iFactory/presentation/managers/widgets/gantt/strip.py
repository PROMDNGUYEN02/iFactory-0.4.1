# File: ui/widgets/gantt/strip.py
"""
Gantt Strip Widget - Presentation Layer (Qt)

High-performance timeline strip widget with interactive segments.
"""
from __future__ import annotations
from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget
from .theme import GanttThemeProvider
from .utils import (
    calculate_hour_step,
    calculate_segment_rect,
    calculate_ticks,
    format_duration,
    time_to_x,
    x_to_time,
)

__all__ = ["GanttStrip"]
Segment = Tuple[datetime, datetime, Optional[str]]


class GanttStrip(QWidget):
    """
    High-performance timeline strip widget.

    Features:
    - Optimized painting with caching
    - Binary search for segment lookup (bisect)
    - Interactive hover/click
    - Real-time "now" line
    - Clipping to current time
    - Responsive axis labels

    Signals:
        segmentClicked: Emitted when segment is clicked
        segmentSelected: Emitted when segment is selected
    """

    __slots__ = (
        "_segments",
        "_starts",
        "_start_time",
        "_end_time",
        "_title",
        "_placeholder",
        "_theme",
        "_show_axis",
        "_show_now",
        "_show_labels",
        "_show_summary",
        "_clip_now",
        "_hover_x",
        "_hover_seg",
        "_sel_seg",
        "_cursor_pointing",
        "_tooltip_last",
        "_chart_rect",
        "_dirty",
        "_color_cache",
        "_ticks",
        "_destroyed",
    )
    segmentClicked = Signal(object)
    segmentSelected = Signal(object)
    ML = 60
    MR = 10
    MT = 4
    MB_AXIS = 18
    MB_NO = 4

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._destroyed = False
        self._segments: List[Segment] = []
        self._starts: List[datetime] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._title = ""
        self._placeholder = "Click a device to view timeline"
        self._theme = "light"
        self._show_axis = True
        self._show_now = True
        self._show_labels = True
        self._show_summary = False
        self._clip_now = True
        self._hover_x: Optional[float] = None
        self._hover_seg: Optional[Segment] = None
        self._sel_seg: Optional[Segment] = None
        self._cursor_pointing = False
        self._tooltip_last = ""
        self._chart_rect = QRectF()
        self._dirty = True
        self._color_cache: Dict[Optional[str], QColor] = {}
        self._ticks: List[datetime] = []
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self.setMinimumHeight(40)

    def _is_valid(self) -> bool:
        """Check if widget is still valid (not destroyed)."""
        if self._destroyed:
            return False
        try:
            self.isVisible()
            return True
        except RuntimeError:
            self._destroyed = True
            return False

    def sizeHint(self) -> QSize:
        """Get size hint."""
        return QSize(600, 50)

    def set_data(self, segments: List[Segment], start: datetime, end: datetime) -> None:
        """
        Set timeline data.

        Args:
            segments: List of (start, end, status) tuples
            start: Timeline start time
            end: Timeline end time
        """
        self._segments = sorted(segments or [], key=lambda x: x[0])
        self._starts = [s for (s, _, _) in self._segments]
        self._start_time = start
        self._end_time = end
        self._reset()
        self._invalidate()
        self.update()

    def set_segments(self, code: str, segments: List[Segment], day_start: datetime, day_end: datetime) -> None:
        """
        Set segments with device code (convenience method).

        Args:
            code: Device code for title
            segments: Segment list
            day_start: Day start time
            day_end: Day end time
        """
        self._title = code
        self.set_data(segments, day_start, day_end)

    def set_title(self, title: str) -> None:
        """Set chart title."""
        self._title = title or ""
        self.update()

    def set_placeholder(self, text: str) -> None:
        """Set placeholder text for empty state."""
        self._placeholder = text or "No data"
        self.update()

    def set_theme(self, theme: str) -> None:
        """Set theme (light/dark)."""
        self._theme = "dark" if theme == "dark" else "light"
        self._color_cache.clear()
        self.update()

    def set_axis_visible(self, visible: bool) -> None:
        """Show/hide time axis."""
        self._show_axis = bool(visible)
        self._invalidate()
        self.update()

    def set_now_line_visible(self, visible: bool) -> None:
        """Show/hide 'now' line."""
        self._show_now = bool(visible)
        self.update()

    def set_segment_labels_visible(self, visible: bool) -> None:
        """Show/hide segment labels."""
        self._show_labels = bool(visible)
        self.update()

    def set_show_summary(self, visible: bool) -> None:
        """Show/hide summary statistics."""
        self._show_summary = bool(visible)
        self.update()

    def set_clip_to_now(self, clip: bool) -> None:
        """Enable/disable clipping to current time."""
        self._clip_now = bool(clip)
        self.update()

    def clear_data(self) -> None:
        """Clear all data."""
        self._segments = []
        self._starts = []
        self._start_time = None
        self._end_time = None
        self._reset()
        self._invalidate()
        self.update()

    def get_selected_segment(self) -> Optional[Segment]:
        """Get currently selected segment."""
        return self._sel_seg

    def _reset(self) -> None:
        """Reset interaction state."""
        self._hover_x = None
        self._hover_seg = None
        self._sel_seg = None
        self._tooltip_last = ""

    def _invalidate(self) -> None:
        """Invalidate caches."""
        self._dirty = True
        self._color_cache.clear()

    def _display_end(self) -> datetime:
        """Get effective end time (clipped to now if enabled)."""
        now = datetime.now()
        if self._clip_now and self._end_time:
            return min(now, self._end_time)
        return self._end_time or now

    def _clipped_segments(self) -> List[Segment]:
        """Get segments clipped to visible range."""
        if not self._segments:
            return []
        end = self._display_end()
        result = []
        for s, e, st in self._segments:
            if s >= end or (self._start_time and e <= self._start_time):
                continue
            actual_end = min(e, end)
            actual_start = max(s, self._start_time) if self._start_time and s < self._start_time else s
            if actual_start < actual_end:
                result.append((actual_start, actual_end, st))
        return result

    def _colors(self) -> Dict:
        """Get theme colors."""
        return GanttThemeProvider.get_colors(self._theme)

    def _status_color(self, status: Optional[str]) -> QColor:
        """Get cached status color."""
        if status not in self._color_cache:
            self._color_cache[status] = QColor(GanttThemeProvider.get_status_color(status, self._theme))
        return self._color_cache[status]

    def _to_x(self, t: datetime) -> float:
        """Convert time to x coordinate."""
        if not self._start_time or not self._end_time:
            return self._chart_rect.left()
        return time_to_x(
            t,
            self._start_time,
            self._end_time,
            self._chart_rect.left(),
            self._chart_rect.width(),
        )

    def _to_time(self, x: float) -> Optional[datetime]:
        """Convert x coordinate to time."""
        if not self._start_time or not self._end_time:
            return None
        return x_to_time(
            x,
            self._start_time,
            self._end_time,
            self._chart_rect.left(),
            self._chart_rect.width(),
        )

    def _find_seg(self, t: datetime) -> Optional[Segment]:
        """
        Find segment at time (binary search).

        Args:
            t: Time to search

        Returns:
            Segment or None
        """
        if not self._segments or not t:
            return None
        if self._clip_now and t > datetime.now():
            return None
        i = bisect_right(self._starts, t) - 1
        if i >= 0:
            (s, e, st) = self._segments[i]
            display_end = min(e, self._display_end()) if self._clip_now else e
            if s <= t < display_end:
                return (s, e, st)
        return None
        return None

    def _seg_rect(self, s: datetime, e: datetime, clip: bool = True) -> QRectF:
        """Calculate segment rectangle."""
        if not self._start_time or not self._end_time:
            return QRectF()
        actual_end = min(e, self._display_end()) if clip and self._clip_now else e
        if s >= actual_end:
            return QRectF()
        (x, y, w, h) = calculate_segment_rect(
            s,
            actual_end,
            self._start_time,
            self._end_time,
            self._chart_rect.left(),
            self._chart_rect.top(),
            self._chart_rect.width(),
            self._chart_rect.height(),
        )
        return QRectF(x, y, w, h) if w > 0 else QRectF()

    def _recalc(self) -> None:
        """Recalculate layout and ticks."""
        r = self.rect()
        mb = self.MB_AXIS if self._show_axis else self.MB_NO
        self._chart_rect = QRectF(self.ML, self.MT, r.width() - self.ML - self.MR, r.height() - self.MT - mb)
        if self._start_time and self._end_time:
            step = calculate_hour_step(self._chart_rect.width())
            self._ticks = calculate_ticks(self._start_time, self._end_time, step)
        else:
            self._ticks = []
        self._dirty = False

    @staticmethod
    def _luminance(color: QColor) -> float:
        """Calculate relative luminance."""
        return 0.2126 * color.redF() + 0.7152 * color.greenF() + 0.0722 * color.blueF()

    def _contrast_color(self, bg: QColor) -> QColor:
        """Get contrasting text color for background."""
        return QColor(Qt.black) if self._luminance(bg) > 0.5 else QColor(Qt.white)

    def resizeEvent(self, event) -> None:
        """Handle resize."""
        if not self._is_valid():
            return
        try:
            super().resizeEvent(event)
            self._dirty = True
        except RuntimeError:
            pass

    def leaveEvent(self, event) -> None:
        """Handle mouse leave."""
        if not self._is_valid():
            return
        self._hover_x = None
        self._hover_seg = None
        self._set_cursor(False)
        if self._tooltip_last:
            try:
                QToolTip.hideText()
            except RuntimeError:
                pass
            self._tooltip_last = ""
        try:
            self.update()
            super().leaveEvent(event)
        except RuntimeError:
            pass

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move."""
        if not self._is_valid():
            return
        if not self._start_time or not self._end_time:
            try:
                super().mouseMoveEvent(event)
            except RuntimeError:
                pass
            return
        if self._dirty:
            self._recalc()
        pos = event.position() if hasattr(event, "position") else event.pos()
        (x, y) = (float(pos.x()), float(pos.y()))
        if self._chart_rect.contains(QPointF(x, y)):
            t = self._to_time(x)
            prev = self._hover_seg
            self._hover_x = x
            seg = self._find_seg(t) if t else None
            self._hover_seg = seg
            self._set_cursor(bool(seg))
            if t:
                self._show_tooltip(t, seg, event)
            if seg != prev:
                try:
                    self.update()
                except RuntimeError:
                    return
        elif self._hover_x is not None:
            self._hover_x = None
            self._hover_seg = None
            self._set_cursor(False)
            try:
                QToolTip.hideText()
            except RuntimeError:
                pass
            self._tooltip_last = ""
            try:
                self.update()
            except RuntimeError:
                return
        try:
            super().mouseMoveEvent(event)
        except RuntimeError:
            pass

    def _set_cursor(self, pointing: bool) -> None:
        """Set cursor shape."""
        if self._cursor_pointing != pointing:
            self._cursor_pointing = pointing
            self.setCursor(QCursor(Qt.PointingHandCursor if pointing else Qt.ArrowCursor))

    def _show_tooltip(self, t: datetime, seg: Optional[Segment], event) -> None:
        """Show tooltip at time."""
        ts = t.strftime("%H:%M:%S")
        now = datetime.now()
        if self._clip_now and t > now:
            text = f"Time: {ts}\n(Future - no data yet)"
        elif seg:
            (s, end, st) = seg
            display_end = min(end, now) if self._clip_now and end > now else end
            dur = (display_end - s).total_seconds()
            ongoing = end > now
            status_text = f"{st or 'Unknown'}" + (" (ongoing)" if ongoing else "")
            end_text = "now" if ongoing else end.strftime("%H:%M")
            text = f"Time: {ts}\nStatus: {status_text}\nDuration: {format_duration(dur)}\n{s.strftime('%H:%M')} → {end_text}"
        else:
            text = f"Time: {ts}\nNo data"
        if text != self._tooltip_last:
            gp = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            QToolTip.showText(gp, text, self, QRect(), 5000)
            self._tooltip_last = text

    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        if not self._is_valid():
            return
        if event.button() == Qt.LeftButton and self._hover_seg:
            self._sel_seg = self._hover_seg
            try:
                self.segmentClicked.emit(self._sel_seg)
                self.segmentSelected.emit(self._sel_seg)
                self.update()
            except RuntimeError:
                return
        try:
            super().mousePressEvent(event)
        except RuntimeError:
            pass

    def paintEvent(self, event) -> None:
        """Paint widget."""
        if not self._is_valid():
            return
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            try:
                if self._dirty:
                    self._recalc()
                self._paint(painter)
            finally:
                painter.end()
        except RuntimeError:
            pass

    def _paint(self, p: QPainter) -> None:
        """Main paint method."""
        colors = self._colors()
        rect = self.rect()
        bg = QColor(colors.get("surface", "#ffffff"))
        text = QColor(colors.get("text", "#1a1a1a"))
        text_alt = QColor(colors.get("text_alt", "#666666"))
        border = QColor(colors.get("border", "#e0e0e0"))
        primary = QColor(colors.get("primary", "#0078d4"))
        p.fillRect(rect, bg)
        p.setPen(QPen(border, 1))
        p.drawRect(self._chart_rect.adjusted(0, 0, -1, -1))
        self._draw_title(p, text)
        if not self._segments or not self._start_time or (not self._end_time):
            self._draw_placeholder(p, text_alt)
            return
        self._draw_future(p)
        for s, e, st in self._clipped_segments():
            seg_rect = self._seg_rect(s, e, clip=False)
            if seg_rect.isNull():
                continue
            fill = QColor(self._status_color(st))
            fill.setAlpha(200 if self._theme == "dark" else 180)
            p.fillRect(seg_rect, fill)
        if self._show_axis:
            self._draw_axis(p, text, text_alt)
        if self._show_now:
            self._draw_now(p, primary)
        if self._show_labels:
            self._draw_labels(p)
        self._draw_outlines(p, primary)
        if self._show_summary:
            self._draw_summary(p, text)

    def _draw_title(self, p: QPainter, color: QColor) -> None:
        """Draw title."""
        if not self._title:
            return
        p.setPen(color)
        font = QFont(p.font())
        font.setPointSizeF(9)
        font.setBold(True)
        p.setFont(font)
        title_rect = QRectF(4, self.MT, self._chart_rect.width(), self._chart_rect.height())
        text = self._title[:10] + "…" if len(self._title) > 10 else self._title
        p.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

    def _draw_placeholder(self, p: QPainter, color: QColor) -> None:
        """Draw placeholder text."""
        p.setPen(color)
        font = QFont(p.font())
        font.setPointSizeF(10)
        p.setFont(font)
        msg = f"{self._title}: No data" if self._title else self._placeholder
        p.drawText(self._chart_rect, Qt.AlignCenter, msg)

    def _draw_future(self, p: QPainter) -> None:
        """Draw future area overlay."""
        if not self._clip_now or not self._start_time or (not self._end_time):
            return
        now = datetime.now()
        if now >= self._end_time:
            return
        if now <= self._start_time:
            future_rect = self._chart_rect
        else:
            now_x = self._to_x(now)
            future_rect = QRectF(
                now_x,
                self._chart_rect.top(),
                self._chart_rect.right() - now_x,
                self._chart_rect.height(),
            )
        if future_rect.width() > 0:
            p.fillRect(future_rect, QColor(128, 128, 128, 30))

    def _draw_axis(self, p: QPainter, text_color: QColor, grid_color: QColor) -> None:
        """Draw time axis."""
        font = QFont(p.font())
        font.setPointSizeF(8)
        p.setFont(font)
        now = datetime.now()
        for t in self._ticks:
            x = self._to_x(t)
            major = t.hour in (0, 6, 12, 18)
            future = self._clip_now and t > now
            line = QColor(grid_color)
            line.setAlpha(30 if future else 60)
            pen = QPen(line, 1.5 if major else 1)
            pen.setStyle(Qt.DotLine)
            p.setPen(pen)
            p.drawLine(
                int(x),
                int(self._chart_rect.top()),
                int(x),
                int(self._chart_rect.bottom()),
            )
            label_color = QColor(text_color)
            if future:
                label_color.setAlpha(100)
            p.setPen(label_color)
            label = t.strftime("%H:%M") if major else t.strftime("%H")
            p.drawText(
                QRectF(x - 20, self._chart_rect.bottom() + 2, 40, 14),
                Qt.AlignHCenter | Qt.AlignTop,
                label,
            )

    def _draw_now(self, p: QPainter, color: QColor) -> None:
        """Draw 'now' line."""
        if not self._start_time or not self._end_time:
            return
        now = datetime.now()
        if not self._start_time <= now <= self._end_time:
            return
        x = self._to_x(now)
        p.setPen(QPen(color, 2))
        p.drawLine(int(x), int(self._chart_rect.top()), int(x), int(self._chart_rect.bottom()))
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        sz = 5
        p.drawPolygon(
            [
                QPointF(x, self._chart_rect.top()),
                QPointF(x - sz, self._chart_rect.top() - sz),
                QPointF(x + sz, self._chart_rect.top() - sz),
            ]
        )
        font = QFont(p.font())
        font.setPointSizeF(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(color)
        p.drawText(
            QRectF(x - 15, self._chart_rect.top() - sz - 12, 30, 12),
            Qt.AlignCenter,
            "NOW",
        )

    def _draw_labels(self, p: QPainter) -> None:
        """Draw segment labels."""
        segs = self._clipped_segments()
        if len(segs) > 50:
            return
        font = QFont(p.font())
        font.setPointSizeF(7)
        font.setBold(True)
        p.setFont(font)
        for s, e, st in segs:
            seg_rect = self._seg_rect(s, e, clip=False)
            if seg_rect.isNull() or seg_rect.width() < 35 or seg_rect.height() < 12:
                continue
            text_color = self._contrast_color(self._status_color(st))
            p.setPen(text_color)
            label = (st or "?").upper()[:6]
            p.drawText(seg_rect.adjusted(3, 0, -3, 0), Qt.AlignVCenter | Qt.AlignLeft, label)

    def _draw_outlines(self, p: QPainter, color: QColor) -> None:
        """Draw selection and hover outlines."""
        if self._sel_seg:
            (s, e, _) = self._sel_seg
            seg_rect = self._seg_rect(s, e, clip=True)
            if not seg_rect.isNull():
                p.setPen(QPen(color, 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(seg_rect.adjusted(1, 1, -1, -1), 3, 3)
        if self._hover_seg and self._hover_seg != self._sel_seg:
            (s, e, _) = self._hover_seg
            seg_rect = self._seg_rect(s, e, clip=True)
            if not seg_rect.isNull():
                hover_color = QColor(color)
                hover_color.setAlpha(150)
                pen = QPen(hover_color, 1.5)
                pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(seg_rect.adjusted(1, 1, -1, -1), 3, 3)

    def _draw_summary(self, p: QPainter, color: QColor) -> None:
        """Draw summary statistics."""
        segs = self._clipped_segments()
        if not segs:
            return
        totals: Dict[str, float] = {}
        for s, e, st in segs:
            key = st or "unknown"
            totals[key] = totals.get(key, 0) + (e - s).total_seconds()
        font = QFont(p.font())
        font.setPointSizeF(8)
        p.setFont(font)
        p.setPen(color)
        parts = [f"{k}: {format_duration(v)}" for (k, v) in sorted(totals.items())]
        text = " | ".join(parts[:4])
        rect = QRectF(self.ML, self.height() - 16, self._chart_rect.width(), 14)
        p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)

    def cleanup(self) -> None:
        """Cleanup before destruction."""
        self._destroyed = True
        self._segments = []
        self._starts = []
        self._color_cache.clear()

    def deleteLater(self) -> None:
        """Override to mark as destroyed."""
        self._destroyed = True
        try:
            super().deleteLater()
        except RuntimeError:
            pass
