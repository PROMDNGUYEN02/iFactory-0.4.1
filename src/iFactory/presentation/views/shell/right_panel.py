"""
Right Panel - Device details view.

MVVM Architecture:
- Binds to DeviceListViewModel for selection
- Binds to ShellViewModel for panel state
- Displays selected device details
- Auto-closes when clicking outside (except on devices)
- Updates content when different device selected without close/reopen
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import (
    select_right_panel_expanded,
    select_selected_device_id,
    select_theme,
    select_devices,
)

if TYPE_CHECKING:
    from ...state.store import Store
    from ...viewmodels import DeviceListViewModel, ShellViewModel

logger = logging.getLogger(__name__)


class RightPanelView:
    """
    Right panel showing device details.

    Passive view that:
    - Binds to ViewModel signals
    - Displays selected device information
    - Renders based on state
    - Supports seamless device switching without panel flicker
    """

    def __init__(
        self,
        container: QFrame,
        store: "Store",
        device_vm: "DeviceListViewModel",
        shell_vm: "ShellViewModel",
    ):
        self._container = container
        self._store = store
        self._device_vm = device_vm
        self._shell_vm = shell_vm
        self._theme_manager = get_theme_manager()
        self._current_theme = "light"
        self._last_device_id: Optional[str] = None
        self._last_render_data: Optional[Dict] = None
        self._is_panel_open = False

        self._layout: Optional[QVBoxLayout] = None
        self._setup()
        self._bind_viewmodels()

    def _bind_viewmodels(self) -> None:
        """Bind to ViewModel signals."""
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.rightPanelChanged.connect(self._on_panel_changed)

    @Slot(object)
    def _on_selection_changed(self, selection) -> None:
        """
        Handle device selection change from ViewModel.

        Key behavior:
        - If panel is open and different device selected: update content only
        - If panel is closed and device selected: open panel with content
        - If no selection: show placeholder (panel state unchanged)
        """
        if selection.has_selection:
            device_id = selection.selected_device_id

            # Check if this is a different device than currently shown
            is_different_device = device_id != self._last_device_id

            device = self._device_vm.selected_device
            if device:
                # Update content - panel state handled by ViewModel
                self._render_device_from_model(device)
                self._last_device_id = device_id

                if is_different_device:
                    logger.debug(f"[RightPanelView] Updated content for device: {device_id}")
            else:
                self._show_loading_device(device_id)
        else:
            self._show_no_selection()
            self._last_device_id = None

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_styles()

    @Slot(bool)
    def _on_panel_changed(self, expanded: bool) -> None:
        """Handle panel expansion change."""
        self._is_panel_open = expanded
        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if not expanded:
            # Panel closing - clear last device to allow fresh render on reopen
            self._last_device_id = None
            logger.debug("[RightPanelView] Panel closed")
        else:
            logger.debug("[RightPanelView] Panel opened")

    @property
    def is_open(self) -> bool:
        """Check if panel is currently open."""
        return self._is_panel_open

    @property
    def current_device_id(self) -> Optional[str]:
        """Get the currently displayed device ID."""
        return self._last_device_id

    def _setup(self) -> None:
        if not self._container:
            return

        self._layout = self._container.layout()
        if not self._layout:
            self._layout = QVBoxLayout(self._container)

        self._clear_layout()

        self._layout.setContentsMargins(16, 20, 16, 20)
        self._layout.setSpacing(12)

        # Header row
        header_layout = QHBoxLayout()
        self._title = QLabel("SELECT DEVICE")
        self._title.setObjectName("panel_title")
        self._status_badge = QLabel("N/A")
        self._status_badge.setObjectName("status_badge")
        self._status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self._title)
        header_layout.addStretch()
        header_layout.addWidget(self._status_badge)
        self._layout.addLayout(header_layout)

        # Description
        self._desc = QLabel("")
        self._desc.setObjectName("device_description")
        self._desc.setWordWrap(True)
        self._layout.addWidget(self._desc)

        # Last update
        self._last_update = QLabel("Last Update: --")
        self._last_update.setObjectName("last_update")
        self._layout.addWidget(self._last_update)

        # Material info frame
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

        # OEE progress
        self._lbl_oee = QLabel("OEE: 0%")
        self._bar_oee = QProgressBar()
        self._bar_oee.setTextVisible(False)
        self._bar_oee.setFixedHeight(8)
        self._layout.addWidget(self._lbl_oee)
        self._layout.addWidget(self._bar_oee)

        # Yield progress
        self._lbl_yield = QLabel("Yield Rate: 0%")
        self._bar_yield = QProgressBar()
        self._bar_yield.setTextVisible(False)
        self._bar_yield.setFixedHeight(8)
        self._layout.addWidget(self._lbl_yield)
        self._layout.addWidget(self._bar_yield)

        # Details frame
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

        # Error label
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

    def _render_device_from_model(self, device) -> None:
        """Render device from DeviceDisplayModel."""
        if hasattr(device, "device_id"):
            # DeviceDisplayModel
            self._title.setText(str(device.display_name))
            self._desc.setText(str(device.description) if device.description else "")
            self._desc.setVisible(bool(device.description))

            if device.last_update:
                clean_time = str(device.last_update).replace("T", " ").split(".")[0]
                self._last_update.setText(f"🕒 {clean_time}")
            else:
                self._last_update.setText("🕒 --")

            self._status_badge.setText(str(device.status_name).upper())
            self._status_badge.setStyleSheet(
                f"background-color: {device.status_color}; color: white; font-weight: 600; "
                f"padding: 4px 12px; border-radius: 10px; font-size: 10px;"
            )

            self._batch.setText(f"📦 {device.material_batch}")
            self._fed_time.setText(f"⏰ Fed: {device.feeding_time}")

            oee_val = float(device.oee) if device.oee else 0
            self._lbl_oee.setText(f"OEE: {oee_val:.1f}%")
            self._bar_oee.setValue(int(min(oee_val, 100)))
            bar_color = "#10B981" if oee_val > 85 else ("#F59E0B" if oee_val > 60 else "#EF4444")
            bar_bg = "#334155" if self._current_theme == "dark" else "#E2E8F0"
            self._bar_oee.setStyleSheet(
                f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }} "
                f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}"
            )

            yield_val = float(device.yield_rate) if device.yield_rate else 0
            self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
            self._bar_yield.setValue(int(min(yield_val, 100)))
            self._bar_yield.setStyleSheet(
                f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }} "
                f"QProgressBar::chunk {{ background-color: #3B82F6; border-radius: 4px; }}"
            )

            self._inputs.setText(f"📥 Inputs: {device.input_count:,}")
            self._outputs.setText(f"📦 Outputs: {device.output_count:,}")
            self._cycle.setText(f"⏱️ Cycle: {device.cycle_time}s")

            if device.last_error:
                self._error.setText(f"⚠️ {device.last_error}")
                self._error.setStyleSheet("color: #EF4444; font-weight: 600;")
            else:
                self._error.setText("✅ Healthy")
                self._error.setStyleSheet("color: #10B981;")
        else:
            # Fallback for dict
            self._render_device_info(device, device.get("device_id", "Unknown"))

    def _show_no_selection(self) -> None:
        """Show no device selected state."""
        self._title.setText("SELECT DEVICE")
        self._status_badge.setText("N/A")
        self._status_badge.setStyleSheet("background-color: #64748B; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;")
        self._desc.setText("")
        self._desc.setVisible(False)
        self._last_update.setText("🕒 --")
        self._batch.setText("📦 --")
        self._fed_time.setText("⏰ Fed: --")
        self._lbl_oee.setText("OEE: 0%")
        self._bar_oee.setValue(0)
        self._lbl_yield.setText("Yield: 0%")
        self._bar_yield.setValue(0)
        self._inputs.setText("📥 Inputs: 0")
        self._outputs.setText("📦 Outputs: 0")
        self._cycle.setText("⏱️ Cycle: 0s")
        self._error.setText("--")
        self._error.setStyleSheet("color: #64748B;")

    def _show_loading_device(self, device_id: str) -> None:
        """Show loading state for selected device."""
        self._title.setText(device_id)
        self._status_badge.setText("LOADING")
        self._status_badge.setStyleSheet("background-color: #64748B; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;")
        self._desc.setText("Loading device data...")
        self._desc.setVisible(True)
        self._last_update.setText("🕒 --")
        self._batch.setText("📦 --")
        self._fed_time.setText("⏰ Fed: --")
        self._lbl_oee.setText("OEE: --%")
        self._bar_oee.setValue(0)
        self._lbl_yield.setText("Yield: --%")
        self._bar_yield.setValue(0)
        self._inputs.setText("📥 Inputs: --")
        self._outputs.setText("📦 Outputs: --")
        self._cycle.setText("⏱️ Cycle: --")
        self._error.setText("--")
        self._error.setStyleSheet("color: #64748B;")

    def _render_device_info(self, device: Any, device_id: str) -> None:
        """Render device information from dict (legacy support)."""

        def get_val(key: str, default: Any = None) -> Any:
            if isinstance(device, dict):
                return device.get(key, default)
            return getattr(device, key, default)

        display_name = get_val("display_name") or get_val("equip_name") or device_id
        status_name = get_val("status_name") or "Unknown"
        status_color = get_val("status_color") or "#64748B"
        description = get_val("description") or ""
        last_update = get_val("last_update")
        material_batch = get_val("material_batch") or "--"
        feeding_time = get_val("feeding_time") or "--"
        oee = get_val("oee") or 0
        yield_rate = get_val("yield_rate") or 0
        input_count = get_val("input_count") or 0
        output_count = get_val("output_count") or 0
        cycle_time = get_val("cycle_time") or 0
        last_error = get_val("last_error")

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
        self._bar_oee.setValue(int(min(oee_val, 100)))
        bar_color = "#10B981" if oee_val > 85 else ("#F59E0B" if oee_val > 60 else "#EF4444")
        bar_bg = "#334155" if self._current_theme == "dark" else "#E2E8F0"
        self._bar_oee.setStyleSheet(
            f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}"
        )

        yield_val = float(yield_rate) if yield_rate else 0
        self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
        self._bar_yield.setValue(int(min(yield_val, 100)))
        self._bar_yield.setStyleSheet(
            f"QProgressBar {{ background-color: {bar_bg}; border: none; border-radius: 4px; }} "
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

    def render(self, state: Dict[str, Any]) -> None:
        """
        Render panel based on state.

        Legacy compatibility - primary updates come via ViewModel signals.
        """
        is_expanded = select_right_panel_expanded(state)
        theme = select_theme(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_styles()

        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if is_expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)
        self._is_panel_open = is_expanded

        if not is_expanded:
            return

        device_id = select_selected_device_id(state)

        if not device_id:
            self._show_no_selection()
            self._last_device_id = None
            return

        devices = select_devices(state)
        device = devices.get(device_id)

        if not device:
            self._show_loading_device(device_id)
            return

        if device_id != self._last_device_id or device != self._last_render_data:
            self._render_device_info(device, device_id)
            self._last_device_id = device_id
            self._last_render_data = device


__all__ = ["RightPanelView"]
