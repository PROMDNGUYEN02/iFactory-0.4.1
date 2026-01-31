# File: presentation/views/widgets/legend_widget.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...constants.status import Status
from ...resources.themes import get_theme_manager


class LegendWidget(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._theme_manager = get_theme_manager()
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
        title.setStyleSheet("font-weight: bold; background-color: #64748b; color: white; " "padding: 2px 5px; border-radius: 3px; font-size: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        status_map = [
            ("RUN", Status.get_color(1)),
            ("IDLE", Status.get_color(3)),
            ("TEST", Status.get_color(4)),
            ("ALARM", Status.get_color(5)),
            ("OFF", Status.get_color(0)),
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

    def _get_val(self, obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def render_stats(
        self,
        timeline_data: Dict[str, List[Any]],
        start: datetime,
        end: datetime,
    ) -> None:
        is_dark = self._theme_manager.is_dark
        name_color = "#E0E0E0" if is_dark else "#555555"
        stat_color = "#B0B0B0" if is_dark else "#888888"

        for lbl in self._status_names_labels:
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {name_color};")

        for lbl in self._stats_labels.values():
            lbl.setStyleSheet(f"font-size: 10px; color: {stat_color};")

        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return

        stats = {key: 0.0 for key in self._stats_labels.keys()}

        def get_key(code: int) -> str:
            if code == 1:
                return "RUN"
            if code == 3:
                return "IDLE"
            if code == 4:
                return "TEST"
            if code == 5:
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
                    code = self._get_val(seg, "status_code") or 0
                    key = get_key(int(code))
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


__all__ = ["LegendWidget"]
