# File: presentation/views/shell/right_panel.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import select_gantt_data, select_right_panel_expanded, select_selected_device, select_theme
from ..widgets.gantt_canvas import GanttCanvasWidget

if TYPE_CHECKING:
    from ...controllers.shell_controller import ShellController
    from ...state.store import Store


class RightPanelView:
    def __init__(
        self,
        container: QFrame,
        store: "Store",
        controller: "ShellController",
    ):
        self._container = container
        self._store = store
        self._controller = controller
        self._theme_manager = get_theme_manager()
        self._current_theme = "light"

        self._layout: Optional[QVBoxLayout] = None
        self._setup()

    def _setup(self) -> None:
        if not self._container:
            return

        self._layout = self._container.layout()
        if not self._layout:
            self._layout = QVBoxLayout(self._container)

        self._clear_layout()

        self._layout.setContentsMargins(15, 20, 15, 20)
        self._layout.setSpacing(12)

        header_layout = QHBoxLayout()
        self._title = QLabel("SELECT DEVICE")
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._status_badge = QLabel("N/A")
        self._status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self._title)
        header_layout.addStretch()
        header_layout.addWidget(self._status_badge)
        self._layout.addLayout(header_layout)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._layout.addWidget(self._desc)

        self._last_update = QLabel("Last Update: --")
        self._layout.addWidget(self._last_update)

        self._mat_frame = QFrame()
        mat_layout = QVBoxLayout(self._mat_frame)
        mat_layout.setContentsMargins(5, 5, 5, 5)
        self._batch = QLabel("Batch: --")
        self._batch.setStyleSheet("font-weight: bold;")
        self._fed_time = QLabel("Fed: --")
        self._fed_time.setStyleSheet("font-size: 10px;")
        mat_layout.addWidget(self._batch)
        mat_layout.addWidget(self._fed_time)
        self._layout.addWidget(self._mat_frame)

        self._lbl_oee = QLabel("OEE: 0%")
        self._lbl_oee.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self._bar_oee = QProgressBar()
        self._bar_oee.setTextVisible(False)
        self._bar_oee.setFixedHeight(12)
        self._layout.addWidget(self._lbl_oee)
        self._layout.addWidget(self._bar_oee)

        self._lbl_yield = QLabel("Yield Rate: 0%")
        self._lbl_yield.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self._bar_yield = QProgressBar()
        self._bar_yield.setTextVisible(False)
        self._bar_yield.setFixedHeight(12)
        self._layout.addWidget(self._lbl_yield)
        self._layout.addWidget(self._bar_yield)

        self._details_frame = QFrame()
        self._details_frame.setObjectName("frame_details")
        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)
        self._inputs = QLabel("Inputs: 0")
        self._outputs = QLabel("Outputs: 0")
        self._cycle = QLabel("Cycle Time: 0.0s")
        details_layout.addWidget(self._inputs)
        details_layout.addWidget(self._outputs)
        details_layout.addWidget(self._cycle)
        self._layout.addWidget(self._details_frame)

        self._lbl_gantt = QLabel("Timeline (Last 24h)")
        self._lbl_gantt.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self._layout.addWidget(self._lbl_gantt)

        self._gantt = GanttCanvasWidget(self._container.window(), is_compact=True)
        self._gantt.setFixedHeight(60)
        self._layout.addWidget(self._gantt)

        self._error = QLabel("Last Error: None")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        self._layout.addStretch()
        self._apply_theme_styles("light")

    def _clear_layout(self) -> None:
        if not self._layout:
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _apply_theme_styles(self, mode: str) -> None:
        is_dark = mode == "dark"
        text_primary = "#FFFFFF" if is_dark else "#000000"
        text_secondary = "#B0B0B0" if is_dark else "#555555"
        text_tertiary = "#808080" if is_dark else "#808080"
        bg_card = "#2d2d2d" if is_dark else "#f5f5f5"

        self._title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_primary};")
        self._desc.setStyleSheet(f"font-size: 12px; font-style: italic; color: {text_secondary};")
        self._last_update.setStyleSheet(f"font-size: 11px; margin-bottom: 5px; color: {text_tertiary};")
        self._lbl_gantt.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {text_secondary};")
        self._mat_frame.setStyleSheet(f"background-color: {bg_card}; border-radius: 6px; padding: 6px;")
        self._batch.setStyleSheet(f"font-weight: bold; color: {text_primary};")
        self._fed_time.setStyleSheet(f"font-size: 10px; color: {text_tertiary};")

    def render(self, state: dict) -> None:
        is_expanded = select_right_panel_expanded(state)
        theme = select_theme(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_styles(theme)

        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if is_expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if not is_expanded:
            return

        device = select_selected_device(state)
        if not device:
            self._title.setText("SELECT DEVICE")
            self._status_badge.setText("N/A")
            self._status_badge.setStyleSheet("background-color: #888888; color: white; padding: 4px 10px; border-radius: 12px;")
            return

        device_id = getattr(device, "device_id", None) or (device.get("device_id") if isinstance(device, dict) else "Unknown")
        display_name = getattr(device, "display_name", None) or (device.get("display_name") if isinstance(device, dict) else device_id)
        status_display = getattr(device, "status_name", None) or (device.get("status_name") if isinstance(device, dict) else "Unknown")
        status_color = getattr(device, "status_color", None) or (device.get("status_color") if isinstance(device, dict) else "#888888")
        description = getattr(device, "description", None) or (device.get("description") if isinstance(device, dict) else "")
        last_update = getattr(device, "last_update", None) or (device.get("last_update") if isinstance(device, dict) else None)
        material_batch = getattr(device, "material_batch", None) or (device.get("material_batch") if isinstance(device, dict) else "--")
        feeding_time = getattr(device, "feeding_time", None) or (device.get("feeding_time") if isinstance(device, dict) else "--")
        oee = getattr(device, "oee", None) or (device.get("oee") if isinstance(device, dict) else 0)
        yield_rate = getattr(device, "yield_rate", None) or (device.get("yield_rate") if isinstance(device, dict) else 0)
        input_count = getattr(device, "input_count", None) or (device.get("input_count") if isinstance(device, dict) else 0)
        output_count = getattr(device, "output_count", None) or (device.get("output_count") if isinstance(device, dict) else 0)
        cycle_time = getattr(device, "cycle_time", None) or (device.get("cycle_time") if isinstance(device, dict) else 0)
        last_error = getattr(device, "last_error", None) or (device.get("last_error") if isinstance(device, dict) else None)

        self._title.setText(str(display_name))

        self._desc.setText(str(description) if description else "")
        self._desc.setVisible(bool(description))

        if last_update:
            clean_time = str(last_update).replace("T", " ").split(".")[0]
            self._last_update.setText(f"🕒 Last Status: <b>{clean_time}</b>")
        else:
            self._last_update.setText("🕒 Last Status: --")

        self._status_badge.setText(str(status_display).upper())
        self._status_badge.setStyleSheet(
            f"background-color: {status_color}; color: white; font-weight: bold; " f"padding: 4px 10px; border-radius: 12px; font-size: 11px;"
        )

        self._batch.setText(f"Batch: {material_batch}")
        self._fed_time.setText(f"Fed: {feeding_time}")

        oee_val = float(oee) if oee else 0
        self._lbl_oee.setText(f"OEE: {oee_val:.1f}%")
        self._bar_oee.setValue(int(oee_val))
        bar_color = "#2ecc71" if oee_val > 85 else ("#f1c40f" if oee_val > 60 else "#e74c3c")
        self._bar_oee.setStyleSheet(f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}")

        yield_val = float(yield_rate) if yield_rate else 0
        self._lbl_yield.setText(f"Yield Rate: {yield_val:.1f}%")
        self._bar_yield.setValue(int(yield_val))
        self._bar_yield.setStyleSheet("QProgressBar::chunk { background-color: #3498db; border-radius: 4px; }")

        self._inputs.setText(f"📥 Inputs: <b>{input_count:,}</b>")
        self._outputs.setText(f"📦 Outputs: <b>{output_count:,}</b>")
        self._cycle.setText(f"⏱️ Cycle Time: <b>{cycle_time}s</b>")

        if last_error:
            self._error.setText(f"⚠️ Alert: {last_error}")
            self._error.setStyleSheet("color: #e74c3c; font-weight: bold;")
        else:
            self._error.setText("✅ System Healthy")
            self._error.setStyleSheet("color: #27ae60;")

        gantt_data = select_gantt_data(state)
        if gantt_data and device_id in gantt_data:
            now = datetime.now()
            start = now - timedelta(hours=24)
            self._gantt.render_timeline({device_id: gantt_data[device_id]}, start, now)
        else:
            self._gantt.render_timeline({})


__all__ = ["RightPanelView"]
