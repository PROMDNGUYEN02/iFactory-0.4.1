# File: presentation/views/widgets/legend_widget.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...constants.status import Status, StatusCode
from ...resources.themes import get_theme_manager


class LegendWidget(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._theme_manager = get_theme_manager()
        self.setStyleSheet("background-color: transparent;")
        self._stats_labels: Dict[str, QLabel] = {}
        self._status_names_labels: Dict[str, QLabel] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        title = QLabel("Status\n(24h)")
        title.setStyleSheet("font-weight: bold; background-color: #64748b; color: white; " "padding: 2px 5px; border-radius: 3px; font-size: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Use Status class colors for consistency
        status_map = [
            ("RUN", Status.get_color(StatusCode.RUNNING), StatusCode.RUNNING),
            ("STOP", Status.get_color(StatusCode.STOPPED), StatusCode.STOPPED),
            ("MAINT", Status.get_color(StatusCode.MAINTENANCE), StatusCode.MAINTENANCE),
            ("ALARM", Status.get_color(StatusCode.ALARM), StatusCode.ALARM),
            ("OFF", Status.get_color(StatusCode.SHUTDOWN), StatusCode.SHUTDOWN),
        ]

        for label_text, color, status_code in status_map:
            item = self._create_legend_item(label_text, color, status_code)
            layout.addWidget(item)

    def _create_legend_item(self, label_text: str, color: str, status_code: int) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        color_box = QFrame()
        color_box.setFixedSize(14, 14)
        color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: 1px solid #555;")

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)

        lbl_name = QLabel(label_text)
        lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #555;")
        lbl_name.setProperty("status_code", status_code)
        self._status_names_labels[label_text] = lbl_name

        lbl_stat = QLabel("0.0%")
        lbl_stat.setStyleSheet("font-size: 10px; color: #888;")
        lbl_stat.setProperty("status_code", status_code)
        self._stats_labels[label_text] = lbl_stat

        text_layout.addWidget(lbl_name)
        text_layout.addWidget(lbl_stat)

        layout.addWidget(color_box)
        layout.addLayout(text_layout)

        return container

    def _get_val(self, obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def clear_stats(self) -> None:
        """Clear all statistics to default values."""
        is_dark = self._theme_manager.is_dark
        name_color = "#E0E0E0" if is_dark else "#555555"
        stat_color = "#B0B0B0" if is_dark else "#888888"

        for key, lbl in self._status_names_labels.items():
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {name_color};")

        for key, lbl in self._stats_labels.items():
            lbl.setText("0.0%")
            lbl.setStyleSheet(f"font-size: 10px; color: {stat_color};")

    def render_stats(
        self,
        timeline_data: Dict[str, List[Any]],
        start: datetime,
        end: datetime,
    ) -> None:
        """Render statistics from timeline data."""
        is_dark = self._theme_manager.is_dark
        name_color = "#E0E0E0" if is_dark else "#555555"
        stat_color = "#B0B0B0" if is_dark else "#888888"

        for key, lbl in self._status_names_labels.items():
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {name_color};")

        for lbl in self._stats_labels.values():
            lbl.setStyleSheet(f"font-size: 10px; color: {stat_color};")

        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            self.clear_stats()
            return

        # Initialize stats by status code
        stats_by_code = {
            StatusCode.RUNNING: 0.0,
            StatusCode.SHUTDOWN: 0.0,
            StatusCode.STOPPED: 0.0,
            StatusCode.MAINTENANCE: 0.0,
            StatusCode.ALARM: 0.0,
        }

        # Calculate durations from segments
        for segments in timeline_data.values():
            for seg in segments:
                s_start = self._get_val(seg, "start_time")
                s_end = self._get_val(seg, "end_time")

                if not (isinstance(s_start, datetime) and isinstance(s_end, datetime)):
                    continue

                eff_start = max(start, s_start)
                eff_end = min(end, s_end)

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
            if label_key and label_key in self._stats_labels:
                pct = (duration / grand_total) * 100
                self._stats_labels[label_key].setText(f"{pct:.1f}%")


__all__ = ["LegendWidget"]
