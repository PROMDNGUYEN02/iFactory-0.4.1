"""
Right Panel Component - Detailed Device View.
Refactored for Dynamic Theming and Maintainability.
"""

from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar

from ...constants.ui_constants import UIConstants
from ...ui_state.selectors import select_right_panel_expanded, select_selected_device_data, select_gantt_timeline
from ..widgets.gantt_canvas import GanttCanvasWidget
from ...resources.themes.theme_manager import theme_manager


class RightPanelView:
    """
    Manages the right-side details panel.
    """

    def __init__(self, container_frame: QFrame, main_window, controller):
        self._frame = container_frame
        self._controller = controller
        self._current_theme_mode = "light"

        if not self._frame.layout():
            QVBoxLayout(self._frame)
        self._layout = self._frame.layout()

        self._setup_ui(main_window)

    def _setup_ui(self, main_window):
        self._clear_layout()

        self._layout.setContentsMargins(15, 20, 15, 20)
        self._layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        self._title = QLabel("SELECT DEVICE")
        self._title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._status_badge = QLabel("N/A")
        self._status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self._title)
        header_layout.addStretch()
        header_layout.addWidget(self._status_badge)
        self._layout.addLayout(header_layout)

        # Description
        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._layout.addWidget(self._desc)

        # Last Update
        self._last_update = QLabel("Last Update: --")
        self._layout.addWidget(self._last_update)

        # Material Info
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

        # OEE & Yield
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

        # Details Box
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

        # Gantt
        self._lbl_gantt = QLabel("Timeline (Last 24h)")
        self._lbl_gantt.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self._layout.addWidget(self._lbl_gantt)

        self._gantt = GanttCanvasWidget(main_window, is_compact=True)
        self._gantt.setFixedHeight(60)
        self._layout.addWidget(self._gantt)

        # Error
        self._error = QLabel("Last Error: None")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        self._layout.addStretch()

        # Apply initial styles
        self._apply_theme_styles("light")

    def _clear_layout(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _apply_theme_styles(self, mode: str):
        """Dynamic stylesheet application for Dark/Light mode."""
        is_dark = mode == "dark"
        text_primary = "#FFFFFF" if is_dark else "#000000"
        text_secondary = "#B0B0B0" if is_dark else "#555555"
        text_tertiary = "#808080" if is_dark else "#808080"
        bg_card = "#2d2d2d" if is_dark else "#f5f5f5"

        # Labels
        self._title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_primary};")
        self._desc.setStyleSheet(f"font-size: 12px; font-style: italic; color: {text_secondary};")
        self._last_update.setStyleSheet(f"font-size: 11px; margin-bottom: 5px; color: {text_tertiary};")
        self._lbl_gantt.setStyleSheet(f"font-weight: bold; margin-top: 10px; color: {text_secondary};")

        # Material Box
        self._mat_frame.setStyleSheet(f"background-color: {bg_card}; border-radius: 6px; padding: 6px;")
        self._batch.setStyleSheet(f"font-weight: bold; color: {text_primary};")
        self._fed_time.setStyleSheet(f"font-size: 10px; color: {text_tertiary};")

        # Details Box (relying on object name styling from main.qss usually, but enforced here for safety)
        # self._details_frame styling is handled by global stylesheet via object name "frame_details"

    def render(self, state: dict):
        """Update right panel content."""
        is_expanded = select_right_panel_expanded(state)

        # Check theme change
        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._apply_theme_styles(new_theme)

        # Animate/Set Width
        width = UIConstants.RIGHT_PANEL_WIDTH_EXPANDED if is_expanded else UIConstants.RIGHT_PANEL_WIDTH_COLLAPSED
        self._frame.setFixedWidth(width)

        if not is_expanded:
            return

        data = select_selected_device_data(state)
        if not data:
            return

        # Render Content
        self._title.setText(data.get("display_name"))

        desc = data.get("description", "")
        self._desc.setText(desc)
        self._desc.setVisible(bool(desc))

        last_up = data.get("last_update")
        if last_up:
            clean_time = str(last_up).replace("T", " ").split(".")[0]
            self._last_update.setText(f"🕒 Last Status: <b>{clean_time}</b>")
        else:
            self._last_update.setText("🕒 Last Status: --")

        status = data.get("status_display", "Offline")
        color = data.get("status_color", "#888888")
        self._status_badge.setText(status.upper())
        self._status_badge.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; " f"padding: 4px 10px; border-radius: 12px; font-size: 11px;"
        )

        self._batch.setText(f"Batch: {data.get('material_batch', '--')}")
        self._fed_time.setText(f"Fed: {data.get('feeding_time', '--')}")

        oee = data.get("oee", 0)
        self._lbl_oee.setText(f"OEE: {oee}%")
        self._bar_oee.setValue(int(oee))
        bar_color = "#2ecc71" if oee > 85 else ("#f1c40f" if oee > 60 else "#e74c3c")
        self._bar_oee.setStyleSheet(f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}")

        yield_rate = data.get("yield_rate", 0)
        self._lbl_yield.setText(f"Yield Rate: {yield_rate}%")
        self._bar_yield.setValue(int(yield_rate))
        self._bar_yield.setStyleSheet("QProgressBar::chunk { background-color: #3498db; border-radius: 4px; }")

        self._inputs.setText(f"📥 Inputs: <b>{data.get('input_count', 0):,}</b>")
        self._outputs.setText(f"📦 Outputs: <b>{data.get('output_count', 0):,}</b>")
        self._cycle.setText(f"⏱️ Cycle Time: <b>{data.get('cycle_time', 0.0)}s</b>")

        # Error
        error_msg = data.get("last_error") or "None"
        if error_msg == "None":
            self._error.setText("✅ System Healthy")
            self._error.setStyleSheet("color: #27ae60;")
        else:
            self._error.setText(f"⚠️ Alert: {error_msg}")
            self._error.setStyleSheet("color: #e74c3c; font-weight: bold;")

        # Update Mini Gantt
        gantt_data = select_gantt_timeline(state)
        dev_id = data.get("id")
        if gantt_data and dev_id in gantt_data:
            now = datetime.now()
            start = now - timedelta(hours=24)
            self._gantt.render_timeline({dev_id: gantt_data[dev_id]}, start, now)
        else:
            self._gantt.render_timeline({})
