from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QFrame, QWidget
from iFactory.config.settings import Settings
from .config import LegendConfig, find_legend_config_path, load_legend_config
from .status_registry import get_status_registry

logger = logging.getLogger(__name__)
__all__ = [
    "StatusLegendWidget",
    "LegendManager",
    "LegendConfig",
    "create_default_legend",
]


def _find_config_path() -> Optional[str]:
    try:
        settings = Settings.instance()
        if hasattr(settings, "get_data_path"):
            p = settings.get_data_path() / "legends.json"
            if p.exists():
                return str(p)
    except Exception:
        pass
    return find_legend_config_path()


LEGENDS_CONFIG_PATH = _find_config_path()


class StatusLegendWidget(QWidget):
    clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None, config: Optional[LegendConfig] = None):
        super().__init__(parent)
        self._config = config or LegendConfig.default()
        self._theme = "light"
        self._hover_index = -1
        self._in_paint = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self.setMouseTracking(True)
        self.setMinimumHeight(20)
        self._segments: List[Tuple[str, float]] = []
        self._total_duration: float = 0.0

    def set_config(self, config: LegendConfig) -> None:
        self._config = config
        self._schedule_update()

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"
        self._schedule_update()

    def update_gantt_data(self, segments: List[Tuple[str, float]]) -> None:
        """
        Update internal stats with Gantt segments.
        Args:
            segments: List of (status_name, duration_seconds)
        """
        self._segments = segments
        self._status_totals: Dict[str, float] = {}
        self._total_duration = 0.0
        for status, duration in segments:
            self._status_totals[status] = self._status_totals.get(status, 0.0) + duration
            self._total_duration += duration
        self._schedule_update()

    def _calc_scale(self) -> float:
        if self._config.ref_width <= 0 or self.width() <= 0:
            return 1.0
        scale = self.width() / self._config.ref_width
        return max(self._config.min_scale, min(self._config.max_scale, scale))

    def _get_rects(self, index: int, scale: float) -> Tuple[QRect, QRect, QRect]:
        box_w = max(20, int(self._config.base_box_width * scale))
        box_h = max(8, int(self._config.base_box_height * scale))
        spacing = max(2, int(self._config.base_spacing * scale))
        title_w = max(30, int(self._config.base_title_width * scale))
        stats_h = int(10 * scale)
        x = title_w + spacing + index * (box_w + spacing)
        y_center = self.height() // 2
        total_h = box_h * 2 + stats_h + 2
        y = y_center - total_h // 2
        color_rect = QRect(x, y, box_w, box_h)
        label_rect = QRect(x, y + box_h + 2, box_w, box_h)
        stats_rect = QRect(x, y + box_h + box_h + 4, box_w, stats_h)
        return (color_rect, label_rect, stats_rect)

    def paintEvent(self, event) -> None:
        if self._in_paint:
            return
        self._in_paint = True
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            scale = self._calc_scale()
            title_w = max(30, int(self._config.base_title_width * scale))
            font_size = max(6, int(self._config.base_font_size * scale))
            title_font_size = max(6, int(self._config.base_title_font_size * scale))
            painter.fillRect(QRect(0, 0, title_w, self.height()), QColor(self._config.title_bg))
            font = QFont("Segoe UI")
            font.setPixelSize(title_font_size)
            font.setBold(True)
            painter.setFont(font)
            text_color = self._config.get_text_color(self._theme)
            painter.setPen(QColor(text_color))
            painter.drawText(
                QRect(0, 0, title_w, self.height()),
                Qt.AlignmentFlag.AlignCenter,
                self._config.title,
            )
            font.setPixelSize(font_size)
            painter.setFont(font)
            font_metrics = QFontMetrics(font)
            for i, status_info in enumerate(self._config.statuses):
                (color_rect, label_rect, stats_rect) = self._get_rects(i, scale)
                if color_rect.right() > self.width():
                    break
                hex_color = status_info.get_color(self._theme)
                painter.fillRect(color_rect, QColor(hex_color))
                if i == self._hover_index:
                    from PySide6.QtGui import QPen

                    painter.setPen(QPen(QColor("#ffffff"), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(color_rect.adjusted(1, 1, -1, -1))
                label = status_info.label
                if font_metrics.horizontalAdvance(label) > label_rect.width():
                    label = font_metrics.elidedText(label, Qt.TextElideMode.ElideRight, label_rect.width())
                painter.setPen(QColor(text_color))
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
                if hasattr(self, "_status_totals") and self._total_duration > 0:
                    status_name = status_info.id
                    duration = self._status_totals.get(status_name, 0.0)
                    if duration > 0:
                        pct = duration / self._total_duration * 100
                        if pct >= 1:
                            h = int(duration // 3600)
                            m = int(duration % 3600 // 60)
                            time_str = f"{h}h" if h > 0 else f"{m}m"
                            stats_text = f"{time_str}\n{pct:.0f}%"
                            stats_font = QFont("Segoe UI")
                            stats_font.setPixelSize(max(5, int(font_size * 0.8)))
                            painter.setFont(stats_font)
                            painter.drawText(
                                stats_rect,
                                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                                stats_text,
                            )
            painter.end()
        finally:
            self._in_paint = False

    def mouseMoveEvent(self, event) -> None:
        scale = self._calc_scale()
        hover = -1
        for i in range(len(self._config.statuses)):
            (color_rect, label_rect, stats_rect) = self._get_rects(i, scale)
            if color_rect.right() > self.width():
                break
            if color_rect.united(label_rect).united(stats_rect).contains(event.pos()):
                hover = i
                break
        if hover != self._hover_index:
            self._hover_index = hover
            self.setCursor(Qt.CursorShape.PointingHandCursor if hover >= 0 else Qt.CursorShape.ArrowCursor)
            self._schedule_update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if 0 <= self._hover_index < len(self._config.statuses):
                self.clicked.emit(self._config.statuses[self._hover_index].id)

    def leaveEvent(self, event) -> None:
        if self._hover_index >= 0:
            self._hover_index = -1
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._schedule_update()

    def sizeHint(self) -> QSize:
        return QSize(self._config.ref_width, self._config.ref_height + 10)

    def _schedule_update(self) -> None:
        if not self._timer.isActive():
            self._timer.start()


class StatusLegendProvider(QObject):

    def __init__(self, config_path: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._path = config_path or LEGENDS_CONFIG_PATH
        self._layout_configs: Dict[str, Dict] = self._load_layout_configs()
        self._legends: Dict[str, StatusLegendWidget] = {}
        self._frames: Dict[str, QFrame] = {}
        self._theme = "light"
        self._in_event = False
        self._resizing: Dict[str, bool] = {}
        self._registry = get_status_registry()

    def _load_layout_configs(self) -> Dict[str, Dict]:
        try:
            if self._path:
                return load_legend_config(self._path)
        except Exception as e:
            logger.error(f"Failed to load legend layout config: {e}")
        return {}

    def register_frame(self, name: str, frame: QFrame, config: Optional[LegendConfig] = None) -> StatusLegendWidget:
        if name in self._legends:
            self._legends[name].deleteLater()
        if config is None:
            if name in self._layout_configs:
                config = LegendConfig.from_dict(self._layout_configs[name])
            else:
                config = LegendConfig.default()
        config.statuses = self._registry.all_statuses
        legend = StatusLegendWidget(frame, config)
        legend.setGeometry(0, 0, frame.width(), frame.height())
        legend.set_theme(self._theme)
        self._legends[name] = legend
        self._frames[name] = frame
        self._resizing[name] = False
        frame.installEventFilter(self)
        legend.show()
        logger.debug(f"Registered legend frame: {name}")
        return legend

    def update_gantt_data(self, segments: List[Tuple[str, float]]) -> None:
        for legend in self._legends.values():
            legend.update_gantt_data(segments)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Resize or self._in_event:
            return False
        self._in_event = True
        try:
            name = next((n for (n, f) in self._frames.items() if f is obj), None)
            if name and (not self._resizing.get(name)) and (name in self._legends):
                self._resizing[name] = True
                self._legends[name].setGeometry(0, 0, self._frames[name].width(), self._frames[name].height())
                self._resizing[name] = False
        finally:
            self._in_event = False
        return False

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"
        for legend in self._legends.values():
            legend.set_theme(self._theme)

    def get_legend(self, name: str) -> Optional[StatusLegendWidget]:
        return self._legends.get(name)

    def dispose(self) -> None:
        for name in list(self._legends.keys()):
            self._legends[name].deleteLater()
            if name in self._frames:
                self._frames[name].removeEventFilter(self)
        self._legends.clear()
        self._frames.clear()
        logger.info("[LegendManager] Disposed")


def create_default_legend(parent: Optional[QWidget] = None) -> StatusLegendWidget:
    config = LegendConfig.default()
    config.statuses = get_status_registry().all_statuses
    return StatusLegendWidget(parent, config)
