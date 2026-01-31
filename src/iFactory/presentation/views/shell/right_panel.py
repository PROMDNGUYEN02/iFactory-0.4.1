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

        self._layout.setContentsMargins(16, 20, 16, 20)
        self._layout.setSpacing(12)

        header_layout = QHBoxLayout()
        self._title = QLabel("SELECT DEVICE")
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
        self._mat_frame.setObjectName("mat_frame")
        mat_layout = QVBoxLayout(self._mat_frame)
        mat_layout.setContentsMargins(10, 10, 10, 10)
        mat_layout.setSpacing(4)
        self._batch = QLabel("Batch: --")
        self._fed_time = QLabel("Fed: --")
        mat_layout.addWidget(self._batch)
        mat_layout.addWidget(self._fed_time)
        self._layout.addWidget(self._mat_frame)

        self._lbl_oee = QLabel("OEE: 0%")
        self._bar_oee = QProgressBar()
        self._bar_oee.setTextVisible(False)
        self._bar_oee.setFixedHeight(8)
        self._layout.addWidget(self._lbl_oee)
        self._layout.addWidget(self._bar_oee)

        self._lbl_yield = QLabel("Yield Rate: 0%")
        self._bar_yield = QProgressBar()
        self._bar_yield.setTextVisible(False)
        self._bar_yield.setFixedHeight(8)
        self._layout.addWidget(self._lbl_yield)
        self._layout.addWidget(self._bar_yield)

        self._details_frame = QFrame()
        self._details_frame.setObjectName("details_frame")
        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(6)
        self._inputs = QLabel("Inputs: 0")
        self._outputs = QLabel("Outputs: 0")
        self._cycle = QLabel("Cycle Time: 0.0s")
        details_layout.addWidget(self._inputs)
        details_layout.addWidget(self._outputs)
        details_layout.addWidget(self._cycle)
        self._layout.addWidget(self._details_frame)

        self._lbl_gantt = QLabel("Timeline (Last 24h)")
        self._layout.addWidget(self._lbl_gantt)

        self._gantt = GanttCanvasWidget(self._container.window(), is_compact=True)
        self._gantt.setFixedHeight(50)
        self._layout.addWidget(self._gantt)

        self._error = QLabel("Last Error: None")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        self._layout.addStretch()
        self._apply_theme_styles()

    def _clear_layout(self) -> None:
        if not self._layout:
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _apply_theme_styles(self) -> None:
        is_dark = self._current_theme == "dark"

        if is_dark:
            bg = "rgba(15, 23, 42, 0.98)"
            border = "rgba(51, 65, 85, 0.5)"
            text_primary = "#F1F5F9"
            text_secondary = "#94A3B8"
            text_muted = "#64748B"
            card_bg = "rgba(30, 41, 59, 0.8)"
            card_border = "rgba(51, 65, 85, 0.6)"
        else:
            bg = "rgba(255, 255, 255, 0.98)"
            border = "rgba(226, 232, 240, 0.5)"
            text_primary = "#1E293B"
            text_secondary = "#475569"
            text_muted = "#64748B"
            card_bg = "rgba(248, 250, 252, 0.8)"
            card_border = "rgba(226, 232, 240, 0.6)"

        self._container.setStyleSheet(
            f"""
            QFrame#right_slide_menu_frame {{
                background-color: {bg};
                border: none;
                border-left: 1px solid {border};
            }}
        """
        )

        self._title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {text_primary};")
        self._desc.setStyleSheet(f"font-size: 11px; color: {text_secondary};")
        self._last_update.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        self._lbl_gantt.setStyleSheet(f"font-weight: 600; margin-top: 8px; color: {text_secondary};")

        self._mat_frame.setStyleSheet(
            f"""
            QFrame#mat_frame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
        """
        )
        self._batch.setStyleSheet(f"font-weight: 600; color: {text_primary};")
        self._fed_time.setStyleSheet(f"font-size: 10px; color: {text_muted};")

        self._lbl_oee.setStyleSheet(f"font-weight: 600; margin-top: 6px; color: {text_primary};")
        self._lbl_yield.setStyleSheet(f"font-weight: 600; margin-top: 4px; color: {text_primary};")

        bar_bg = "#334155" if is_dark else "#E2E8F0"
        self._bar_oee.setStyleSheet(f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }}")
        self._bar_yield.setStyleSheet(f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }}")

        self._details_frame.setStyleSheet(
            f"""
            QFrame#details_frame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
        """
        )
        self._inputs.setStyleSheet(f"color: {text_primary};")
        self._outputs.setStyleSheet(f"color: {text_primary};")
        self._cycle.setStyleSheet(f"color: {text_primary};")

    def render(self, state: dict) -> None:
        is_expanded = select_right_panel_expanded(state)
        theme = select_theme(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_styles()

        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if is_expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if not is_expanded:
            return

        device = select_selected_device(state)
        if not device:
            self._title.setText("SELECT DEVICE")
            self._status_badge.setText("N/A")
            self._status_badge.setStyleSheet("background-color: #64748B; color: white; padding: 4px 10px; border-radius: 10px; font-size: 10px;")
            return

        device_id = getattr(device, "device_id", None) or (device.get("device_id") if isinstance(device, dict) else "Unknown")
        display_name = getattr(device, "display_name", None) or (device.get("display_name") if isinstance(device, dict) else device_id)
        status_name = getattr(device, "status_name", None) or (device.get("status_name") if isinstance(device, dict) else "Unknown")
        status_color = getattr(device, "status_color", None) or (device.get("status_color") if isinstance(device, dict) else "#64748B")
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
            self._last_update.setText(f"🕒 {clean_time}")
        else:
            self._last_update.setText("🕒 --")

        self._status_badge.setText(str(status_name).upper())
        self._status_badge.setStyleSheet(
            f"background-color: {status_color}; color: white; font-weight: 600; " f"padding: 4px 12px; border-radius: 10px; font-size: 10px;"
        )

        self._batch.setText(f"📦 {material_batch}")
        self._fed_time.setText(f"⏰ Fed: {feeding_time}")

        oee_val = float(oee) if oee else 0
        self._lbl_oee.setText(f"OEE: {oee_val:.1f}%")
        self._bar_oee.setValue(int(oee_val))
        bar_color = "#10B981" if oee_val > 85 else ("#F59E0B" if oee_val > 60 else "#EF4444")
        self._bar_oee.setStyleSheet(
            f"QProgressBar {{ background-color: {'#334155' if self._current_theme == 'dark' else '#E2E8F0'}; border: none; border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}"
        )

        yield_val = float(yield_rate) if yield_rate else 0
        self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
        self._bar_yield.setValue(int(yield_val))
        self._bar_yield.setStyleSheet(
            f"QProgressBar {{ background-color: {'#334155' if self._current_theme == 'dark' else '#E2E8F0'}; border: none; border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background-color: #3B82F6; border-radius: 4px; }}"
        )

        self._inputs.setText(f"📥 Inputs: {input_count:,}")
        self._outputs.setText(f"📦 Outputs: {output_count:,}")
        self._cycle.setText(f"⏱️ Cycle: {cycle_time}s")

        if last_error:
            self._error.setText(f"⚠️ {last_error}")
            self._error.setStyleSheet("color: #EF4444; font-weight: 600;")
        else:
            self._error.setText("✅ Healthy")
            self._error.setStyleSheet("color: #10B981;")

        gantt_data = select_gantt_data(state)
        if gantt_data and device_id in gantt_data:
            now = datetime.now()
            start = now - timedelta(hours=24)
            self._gantt.render_timeline({device_id: gantt_data[device_id]}, start, now)
        else:
            self._gantt.render_timeline({})


__all__ = ["RightPanelView"]
