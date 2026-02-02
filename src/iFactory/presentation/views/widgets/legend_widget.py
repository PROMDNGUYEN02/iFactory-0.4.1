# File: presentation/views/widgets/legend_widget.py
"""
Legend Widget - Status statistics display.

Uses ThemeService for consistent theming.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...constants.status import Status, StatusCode

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class LegendItem(QWidget):
    """Individual legend item with color indicator and stats."""

    def __init__(self, label: str, status_code: int, color: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._label = label
        self._status_code = status_code
        self._color = color
        self._theme_service = theme_service

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Color indicator
        self._color_box = QFrame()
        self._color_box.setFixedSize(14, 14)
        layout.addWidget(self._color_box)

        # Text container
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setContentsMargins(0, 0, 0, 0)

        # Label
        self._name_label = QLabel(self._label)
        text_layout.addWidget(self._name_label)

        # Stat value
        self._stat_label = QLabel("0.0%")
        text_layout.addWidget(self._stat_label)

        layout.addLayout(text_layout)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens
        is_dark = self._theme_service.is_dark

        # Color box
        self._color_box.setStyleSheet(
            f"""
            background-color: {self._color};
            border-radius: {tokens.radius_sm};
            border: 1px solid {tokens.border_default};
        """
        )

        # Name label
        name_color = tokens.text_secondary if is_dark else tokens.text_primary
        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_semibold};
            color: {name_color};
        """
        )

        # Stat label
        self._stat_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

    def set_value(self, percent: float) -> None:
        """Update the percentage value."""
        self._stat_label.setText(f"{percent:.1f}%")

    def clear(self) -> None:
        """Reset to default value."""
        self._stat_label.setText("0.0%")


class LegendWidget(QWidget):
    """
    Status legend with statistics.

    Shows status distribution for the visible time range.
    Uses ThemeService for consistent theming.
    """

    # Status configuration: (label, status_code)
    STATUS_CONFIG = [
        ("RUN", StatusCode.RUNNING),
        ("STOP", StatusCode.STOPPED),
        ("MAINT", StatusCode.MAINTENANCE),
        ("ALARM", StatusCode.ALARM),
        ("OFF", StatusCode.SHUTDOWN),
    ]

    def __init__(self, theme_service: Optional["ThemeService"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Get theme service
        if theme_service is None:
            from ...services.theme_service import get_theme_service

            theme_service = get_theme_service()

        self._theme_service = theme_service
        self._legend_items: Dict[str, LegendItem] = {}

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Title badge
        self._title = QLabel("Status\n(24h)")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Create legend items
        for label, status_code in self.STATUS_CONFIG:
            color = Status.get_color(status_code)
            item = LegendItem(label=label, status_code=status_code, color=color, theme_service=self._theme_service, parent=self)
            self._legend_items[label] = item
            layout.addWidget(item)

        layout.addStretch()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        # Container
        self.setStyleSheet("background-color: transparent;")

        # Title badge
        self._title.setStyleSheet(
            f"""
            QLabel {{
                font-weight: {tokens.font_weight_bold};
                background-color: {tokens.text_muted};
                color: {tokens.text_inverse};
                padding: 2px 5px;
                border-radius: {tokens.radius_sm};
                font-size: {tokens.font_size_xs};
            }}
        """
        )

    def clear_stats(self) -> None:
        """Clear all statistics to default values."""
        for item in self._legend_items.values():
            item.clear()

    def render_stats(
        self,
        timeline_data: Dict[str, List[Any]],
        start: datetime,
        end: datetime,
    ) -> None:
        """
        Render statistics from timeline data.

        Args:
            timeline_data: Dict of device_id -> list of segments
            start: Start time of the range
            end: End time of the range
        """
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            self.clear_stats()
            return

        # Initialize stats by status code
        stats_by_code: Dict[int, float] = {
            StatusCode.RUNNING: 0.0,
            StatusCode.SHUTDOWN: 0.0,
            StatusCode.STOPPED: 0.0,
            StatusCode.MAINTENANCE: 0.0,
            StatusCode.ALARM: 0.0,
        }

        # Calculate durations from segments
        for segments in timeline_data.values():
            for seg in segments:
                seg_start = self._get_val(seg, "start_time")
                seg_end = self._get_val(seg, "end_time")

                if not (isinstance(seg_start, datetime) and isinstance(seg_end, datetime)):
                    continue

                # Clip to range
                eff_start = max(start, seg_start)
                eff_end = min(end, seg_end)

                if eff_end > eff_start:
                    duration = (eff_end - eff_start).total_seconds()
                    code = self._get_val(seg, "status_code")
                    if code is not None:
                        code = int(code)
                        if code in stats_by_code:
                            stats_by_code[code] += duration

        # Map status codes to legend labels
        code_to_label = {
            StatusCode.RUNNING: "RUN",
            StatusCode.SHUTDOWN: "OFF",
            StatusCode.STOPPED: "STOP",
            StatusCode.MAINTENANCE: "MAINT",
            StatusCode.ALARM: "ALARM",
        }

        # Calculate percentages
        device_count = len(timeline_data)
        if device_count == 0:
            self.clear_stats()
            return

        grand_total = total_duration * device_count

        for code, duration in stats_by_code.items():
            label_key = code_to_label.get(code)
            if label_key and label_key in self._legend_items:
                pct = (duration / grand_total) * 100
                self._legend_items[label_key].set_value(pct)

    def _get_val(self, obj: Any, key: str) -> Any:
        """Get value from dict or object."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)


__all__ = ["LegendWidget"]
