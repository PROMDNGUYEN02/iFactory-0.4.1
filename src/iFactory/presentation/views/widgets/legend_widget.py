"""
Legend Widget - Status color legend.
Theme-aware with automatic color adaptation and statistical summary.
Refactored for Hybrid Dict/ViewModel Support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget, QVBoxLayout
from ...constants.ui_constants import StatusColors
from ...resources.themes.theme_manager import theme_manager


class LegendWidget(QWidget):
    """Status legend with color indicators and duration stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self._stats_labels: Dict[str, QLabel] = {}
        self._status_names_labels: List[QLabel] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        title = QLabel("Status\n(24h)")
        title.setStyleSheet("font-weight: bold; background-color: #64748b; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        status_map = [
            ("RUN", StatusColors.RUNNING),
            ("IDLE", StatusColors.IDLE),
            ("TEST", StatusColors.TEST),
            ("ALARM", StatusColors.ERROR),
            ("OFF", StatusColors.OFFLINE),
        ]

        for label_text, color in status_map:
            item = self._create_legend_item(label_text, color)
            layout.addWidget(item)

    def _create_legend_item(self, label_text: str, color: str) -> QWidget:
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
        self._status_names_labels.append(lbl_name)

        lbl_stat = QLabel("0.0%")
        lbl_stat.setStyleSheet("font-size: 10px; color: #888;")
        self._stats_labels[label_text] = lbl_stat

        text_layout.addWidget(lbl_name)
        text_layout.addWidget(lbl_stat)

        layout.addWidget(color_box)
        layout.addLayout(text_layout)

        return container

    def _get_val(self, obj, key):
        """Helper to get value from either dict or object."""
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def render_stats(self, timeline_data: Dict[str, List[Any]], start: datetime, end: datetime):
        """
        Calculate and display percentage duration for each status.
        Supports both Dicts and ViewModels.
        """
        # 1. Update Theme Colors
        is_dark = theme_manager.is_dark
        name_color = "#E0E0E0" if is_dark else "#555555"
        stat_color = "#B0B0B0" if is_dark else "#888888"

        for lbl in self._status_names_labels:
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {name_color};")

        for lbl in self._stats_labels.values():
            lbl.setStyleSheet(f"font-size: 10px; color: {stat_color};")

        # 2. Calculate Stats
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return

        stats = {key: 0.0 for key in self._stats_labels.keys()}

        def get_key(code):
            c = int(code)
            if c == 1:
                return "RUN"
            if c == 2:
                return "IDLE"
            if c == 3:
                return "TEST"
            if c == 0 or c > 3:
                return "ALARM"
            return "OFF"

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
                    code = self._get_val(seg, "status_code") or -1
                    key = get_key(code)
                    if key in stats:
                        stats[key] += duration

        device_count = len(timeline_data)
        if device_count == 0:
            return

        grand_total = total_duration * device_count

        for key, duration in stats.items():
            pct = (duration / grand_total) * 100
            if key in self._stats_labels:
                self._stats_labels[key].setText(f"{pct:.1f}%")
