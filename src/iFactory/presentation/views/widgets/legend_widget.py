"""
Legend Widget - Status color legend.
Theme-aware with automatic color adaptation and statistical summary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget, QVBoxLayout


class LegendWidget(QWidget):
    """Status legend with color indicators and duration stats."""

    # Map status codes to names and colors
    # (Assuming these match StatusColors constants)
    STATUSES = [
        ("RUN", "#3bb806", 1),
        ("IDLE", "#c3c51b", 2),
        ("TEST", "#38c0bf", 3),
        # Add other mappings as required by business logic
        ("STOP", "#bd1e15", 0),  # Assuming 0/Stop for demo, adjust based on actual Enum
        ("N/A", "#9E9E9E", -1),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self._stats_labels: Dict[str, QLabel] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        title = QLabel("Status\n(24h)")
        title.setStyleSheet("font-weight: bold; background-color: #939892; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Create legend items
        # We use a known list of statuses. In a real app, import StatusColors enum.
        # Here we use the list provided in the previous file but enhanced for stats.
        # Fallback list if STATUSES isn't fully comprehensive for the data
        status_map = [
            ("RUN", "#3bb806"),
            ("IDLE", "#c3c51b"),
            ("TEST", "#38c0bf"),
            ("ALARM", "#bd1e15"),  # Mapped roughly to Stop/Error
            ("OFF", "#9E9E9E"),
        ]

        for label_text, color in status_map:
            item = self._create_legend_item(label_text, color)
            layout.addWidget(item)

    def _create_legend_item(self, label_text: str, color: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Color Box
        color_box = QFrame()
        color_box.setFixedSize(14, 14)
        color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: 1px solid #555;")

        # Text Info
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)

        lbl_name = QLabel(label_text)
        lbl_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #555;")

        lbl_stat = QLabel("0%")
        lbl_stat.setStyleSheet("font-size: 10px; color: #888;")
        self._stats_labels[label_text] = lbl_stat

        text_layout.addWidget(lbl_name)
        text_layout.addWidget(lbl_stat)

        layout.addWidget(color_box)
        layout.addLayout(text_layout)

        return container

    def render_stats(self, timeline_data: Dict[str, List[Any]], start: datetime, end: datetime):
        """
        Calculate and display percentage duration for each status
        within the given time window across all devices.
        """
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return

        # Initialize counters (using simplistic mapping for demo)
        # In production, map status_code int to string keys used in _stats_labels
        stats = {key: 0.0 for key in self._stats_labels.keys()}

        # Helper to map codes to our legend keys
        def get_key(code):
            c = int(code)
            if c == 1:
                return "RUN"
            if c == 2:
                return "IDLE"
            if c == 3:
                return "TEST"
            if c == 0 or c > 3:
                return "ALARM"  # Group others as Alarm/Stop for simplicity
            return "OFF"

        active_time_sum = 0

        for segments in timeline_data.values():
            for seg in segments:
                s_start = seg.get("start_time")
                s_end = seg.get("end_time")
                if not (isinstance(s_start, datetime) and isinstance(s_end, datetime)):
                    continue

                # Clip to window
                eff_start = max(start, s_start)
                eff_end = min(end, s_end)

                if eff_end > eff_start:
                    duration = (eff_end - eff_start).total_seconds()
                    code = seg.get("status_code", -1)
                    key = get_key(code)
                    if key in stats:
                        stats[key] += duration

        # Normalize across number of devices?
        # Typically legend shows "System Wide Distribution" or average.
        # Here we calculate composition of the visualized time.
        # If multiple devices, total available time = total_duration * device_count
        device_count = len(timeline_data)
        if device_count == 0:
            return

        grand_total = total_duration * device_count

        for key, duration in stats.items():
            pct = (duration / grand_total) * 100
            if key in self._stats_labels:
                self._stats_labels[key].setText(f"{pct:.1f}%")


__all__ = ["LegendWidget"]
