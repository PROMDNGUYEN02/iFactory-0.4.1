"""
Legend Widget - Status statistics display.

Uses ThemeService for consistent theming.
Uses ColorRegistry for cached colors.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...constants.colors import get_color_registry
from ...constants.status import Status, StatusCode

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class LegendItem(QWidget):
    """Individual legend item with color indicator and stats."""

    __slots__ = ("_label", "_status_code", "_color", "_theme_service", "_color_box", "_name_label", "_stat_label")

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

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._color_box = QFrame()
        self._color_box.setFixedSize(14, 14)
        layout.addWidget(self._color_box)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel(self._label)
        text_layout.addWidget(self._name_label)

        self._stat_label = QLabel("0.0%")
        text_layout.addWidget(self._stat_label)

        layout.addLayout(text_layout)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens
        is_dark = self._theme_service.is_dark

        self._color_box.setStyleSheet(
            f"""
            background-color: {self._color};
            border-radius: {tokens.radius_sm};
            border: 1px solid {tokens.border_default};
        """
        )

        name_color = tokens.text_secondary if is_dark else tokens.text_primary
        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_semibold};
            color: {name_color};
        """
        )

        self._stat_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

    def set_value(self, percent: float) -> None:
        self._stat_label.setText(f"{percent:.1f}%")

    def clear(self) -> None:
        self._stat_label.setText("0.0%")


class LegendWidget(QWidget):
    """
    Status legend with statistics.

    Shows status distribution for the visible time range.
    Uses ThemeService for consistent theming.
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
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel("Status\n(24h)")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

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
        for item in self._legend_items.values():
            item.clear()

    def render_stats(
        self,
        timeline_data: Dict[str, List[Any]],
        start: datetime,
        end: datetime,
    ) -> None:
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            self.clear_stats()
            return

        stats_by_code: Dict[int, float] = {
            StatusCode.RUNNING: 0.0,
            StatusCode.SHUTDOWN: 0.0,
            StatusCode.STOPPED: 0.0,
            StatusCode.MAINTENANCE: 0.0,
            StatusCode.ALARM: 0.0,
        }

        for segments in timeline_data.values():
            for seg in segments:
                seg_start = self._get_val(seg, "start_time")
                seg_end = self._get_val(seg, "end_time")

                if not (isinstance(seg_start, datetime) and isinstance(seg_end, datetime)):
                    continue

                eff_start = max(start, seg_start)
                eff_end = min(end, seg_end)

                if eff_end > eff_start:
                    duration = (eff_end - eff_start).total_seconds()
                    code = self._get_val(seg, "status_code")
                    if code is not None:
                        code = int(code)
                        if code in stats_by_code:
                            stats_by_code[code] += duration

        device_count = len(timeline_data)
        if device_count == 0:
            self.clear_stats()
            return

        grand_total = total_duration * device_count

        for code, duration in stats_by_code.items():
            label_key = self.CODE_TO_LABEL.get(code)
            if label_key and label_key in self._legend_items:
                pct = (duration / grand_total) * 100
                self._legend_items[label_key].set_value(pct)

    def _get_val(self, obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)


__all__ = ["LegendWidget", "LegendItem"]
