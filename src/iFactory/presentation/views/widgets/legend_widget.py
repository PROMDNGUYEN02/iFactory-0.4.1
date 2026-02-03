# File: presentation/views/widgets/legend_widget.py
"""
Legend Widget - EQ Status statistics display for 24h period.

FIXED: Properly clip segments to 24h window and validate durations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
)

from ...constants.colors import get_color_registry
from ...constants.status import Status, StatusCode

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


# Constants
SECONDS_PER_DAY = 86400  # 24 hours
SECONDS_PER_HOUR = 3600

# Fixed width for each legend item to prevent jumping
LEGEND_ITEM_WIDTH = 85


class LegendItem(QWidget):
    """
    Individual legend item with fixed width and left-aligned content.

    Layout (fixed width, left-aligned):
    ┌───────────────┐
    │ ■ RUN         │  <- Row 1: color box + name (left-aligned)
    │ 8h30m (35%)   │  <- Row 2: duration (percent) (left-aligned)
    └───────────────┘
    """

    def __init__(
        self,
        label: str,
        status_code: int,
        color: str,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._label = label
        self._status_code = status_code
        self._color = color
        self._theme_service = theme_service
        self._total_seconds: float = 0

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self) -> None:
        # Fixed width to prevent layout jumping
        self.setFixedWidth(LEGEND_ITEM_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Row 1: Color box + Name (LEFT-ALIGNED)
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(4)
        row1.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._color_box = QFrame()
        self._color_box.setFixedSize(12, 12)
        row1.addWidget(self._color_box)

        self._name_label = QLabel(self._label)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row1.addWidget(self._name_label)

        row1.addStretch()
        layout.addLayout(row1)

        # Row 2: Duration (Percent) - LEFT-ALIGNED
        self._stat_label = QLabel("-- (--%)")
        self._stat_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._stat_label)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        # Color box
        self._color_box.setStyleSheet(
            f"""
            background-color: {self._color};
            border-radius: 2px;
            border: 1px solid {tokens.border_default};
        """
        )

        # Name label
        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            font-weight: {tokens.font_weight_bold};
            color: {tokens.text_primary};
        """
        )

        # Stat label (duration + percent) - colored by status
        self._stat_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            font-family: "Consolas", monospace;
            color: {self._color};
            font-weight: {tokens.font_weight_semibold};
        """
        )

    def set_stats(self, total_seconds: float) -> None:
        """
        Update statistics display.

        Args:
            total_seconds: Total seconds for this status (already clipped to 24h max)
        """
        self._total_seconds = total_seconds

        # Format duration
        duration_str = self._format_duration(total_seconds)

        # Calculate percentage of 24h
        percent = (total_seconds / SECONDS_PER_DAY) * 100

        # Display as "8h30m (35.4%)"
        self._stat_label.setText(f"{duration_str} ({percent:.1f}%)")

    def clear(self) -> None:
        """Clear statistics."""
        self._total_seconds = 0
        self._stat_label.setText("-- (--%)")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as 'Xh Ym' or 'Xm' or '0m'."""
        if seconds <= 0:
            return "0m"

        if seconds < 60:
            return f"{int(seconds)}s"

        hours = int(seconds // SECONDS_PER_HOUR)
        minutes = int((seconds % SECONDS_PER_HOUR) // 60)

        if hours > 0:
            if minutes > 0:
                return f"{hours}h{minutes}m"
            return f"{hours}h"
        return f"{minutes}m"


class LegendWidget(QWidget):
    """
    EQ Status legend with statistics for 24h period.

    IMPORTANT: All durations are CLIPPED to the 24h window (start to end).
    Maximum total duration per status = 24 hours.
    """

    STATUS_CONFIG = [
        ("RUN", StatusCode.RUNNING),
        ("STOP", StatusCode.STOPPED),
        ("MAINT", StatusCode.MAINTENANCE),
        ("ALARM", StatusCode.ALARM),
        ("OFF", StatusCode.SHUTDOWN),
    ]

    CODE_TO_LABEL = {
        StatusCode.RUNNING: "RUN",
        StatusCode.SHUTDOWN: "OFF",
        StatusCode.STOPPED: "STOP",
        StatusCode.MAINTENANCE: "MAINT",
        StatusCode.ALARM: "ALARM",
    }

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
        self._legend_items: Dict[str, LegendItem] = {}

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Title section (EQ Status + 24h) - fixed width
        title_container = QWidget()
        title_container.setFixedWidth(55)
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_main = QLabel("EQ Status")
        self._title_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(self._title_main)

        self._title_sub = QLabel("(24h)")
        self._title_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(self._title_sub)

        layout.addWidget(title_container)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #ccc;")
        layout.addWidget(sep)

        # Status items - each with FIXED WIDTH
        for label, status_code in self.STATUS_CONFIG:
            color = Status.get_color(status_code)
            item = LegendItem(
                label=label,
                status_code=status_code,
                color=color,
                theme_service=self._theme_service,
                parent=self,
            )
            self._legend_items[label] = item
            layout.addWidget(item)

        layout.addStretch()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet("background-color: transparent;")

        # Main title style
        self._title_main.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            font-weight: {tokens.font_weight_bold};
            color: {tokens.text_primary};
        """
        )

        # Sub title style
        self._title_sub.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

    def clear_stats(self) -> None:
        """Clear all statistics."""
        for item in self._legend_items.values():
            item.clear()

    def render_stats(
        self,
        timeline_data: Dict[str, List[Any]],
        start: datetime,
        end: datetime,
    ) -> None:
        """
        Render statistics from timeline segments.

        IMPORTANT:
        - All segments are CLIPPED to [start, end] window
        - Percentage = duration / 86400s (24 hours)
        - Maximum duration per status = (end - start) seconds

        Args:
            timeline_data: Dict mapping device_code to list of segments
            start: Start time (00:00 of current day)
            end: End time (24:00 of current day OR current time for future)
        """
        if not timeline_data:
            self.clear_stats()
            return

        # Calculate max allowed duration (should be <= 24h)
        max_duration = (end - start).total_seconds()
        if max_duration <= 0:
            self.clear_stats()
            return

        # Log for debugging
        device_count = len(timeline_data)
        segment_count = sum(len(segs) for segs in timeline_data.values())
        logger.debug(
            f"[Legend] render_stats: {device_count} devices, {segment_count} segments, "
            f"window: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
        )

        # Initialize accumulators
        stats_by_code: Dict[int, float] = {
            StatusCode.RUNNING: 0.0,
            StatusCode.SHUTDOWN: 0.0,
            StatusCode.STOPPED: 0.0,
            StatusCode.MAINTENANCE: 0.0,
            StatusCode.ALARM: 0.0,
        }

        # Aggregate durations from all segments
        for device_code, segments in timeline_data.items():
            for seg in segments:
                duration = self._calculate_clipped_duration(seg, start, end)
                if duration > 0:
                    code = self._get_status_code(seg)
                    if code in stats_by_code:
                        stats_by_code[code] += duration

        # Validate: total should not exceed max_duration
        total_duration = sum(stats_by_code.values())
        if total_duration > max_duration * 1.01:  # Allow 1% tolerance for floating point
            logger.warning(
                f"[Legend] Total duration ({total_duration:.0f}s = {total_duration/3600:.1f}h) "
                f"exceeds window ({max_duration:.0f}s = {max_duration/3600:.1f}h). "
                f"Data may have overlapping segments."
            )

        # Log stats for debugging
        for code, duration in stats_by_code.items():
            if duration > 0:
                label = self.CODE_TO_LABEL.get(code, "?")
                hours = duration / 3600
                percent = (duration / SECONDS_PER_DAY) * 100
                logger.debug(f"[Legend] {label}: {hours:.1f}h ({percent:.1f}%)")

        # Update legend items
        for code, total_duration in stats_by_code.items():
            label_key = self.CODE_TO_LABEL.get(code)
            if label_key and label_key in self._legend_items:
                self._legend_items[label_key].set_stats(total_duration)

    def _calculate_clipped_duration(self, seg: Any, window_start: datetime, window_end: datetime) -> float:
        """
        Calculate duration of segment CLIPPED to the window.

        Returns 0 if segment is outside window or invalid.
        """
        # Get segment times
        seg_start = self._get_val(seg, "start_time")
        seg_end = self._get_val(seg, "end_time")

        # If we have datetime objects, clip properly
        if isinstance(seg_start, datetime) and isinstance(seg_end, datetime):
            # Clip to window
            eff_start = max(seg_start, window_start)
            eff_end = min(seg_end, window_end)

            if eff_end > eff_start:
                return (eff_end - eff_start).total_seconds()
            return 0.0

        # Fallback: use pre-calculated duration BUT validate it
        duration = self._get_val(seg, "duration_seconds")
        if duration and duration > 0:
            # Cap to max possible (24 hours)
            return min(float(duration), SECONDS_PER_DAY)

        return 0.0

    def _get_status_code(self, seg: Any) -> int:
        """Extract status code from segment."""
        code = self._get_val(seg, "status_code")
        if code is None:
            return 0
        try:
            return int(code)
        except (ValueError, TypeError):
            return 0

    def _get_val(self, obj: Any, key: str) -> Any:
        """Get value from dict or object attribute."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)


__all__ = ["LegendWidget", "LegendItem"]
