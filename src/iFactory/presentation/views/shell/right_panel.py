# File: presentation/views/shell/right_panel.py
"""
Right Panel - Device details view.

Uses ThemeService for all styling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from ...constants.layout import Layout
from ...state.selectors import (
    select_right_panel_expanded,
    select_selected_device_id,
    select_devices,
)

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...state.store import Store
    from ...viewmodels import DeviceListViewModel, ShellViewModel

logger = logging.getLogger(__name__)


class RightPanelView:
    """Right panel showing device details using ThemeService."""

    def __init__(
        self,
        container: QFrame,
        store: "Store",
        device_vm: "DeviceListViewModel",
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
    ):
        self._container = container
        self._store = store
        self._device_vm = device_vm
        self._shell_vm = shell_vm
        self._theme_service = theme_service
        self._last_device_id: Optional[str] = None
        self._last_render_data: Optional[Dict] = None
        self._is_panel_open = False

        self._layout: Optional[QVBoxLayout] = None
        self._setup()
        self._apply_theme_styles()
        self._bind_viewmodels()

    def _bind_viewmodels(self) -> None:
        """Bind to ViewModel signals."""
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.rightPanelChanged.connect(self._on_panel_changed)

    @Slot(object)
    def _on_selection_changed(self, selection) -> None:
        """Handle device selection change."""
        if selection.has_selection:
            device_id = selection.selected_device_id
            is_different_device = device_id != self._last_device_id

            device = self._device_vm.selected_device
            if device:
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
        self._apply_theme_styles()

    @Slot(bool)
    def _on_panel_changed(self, expanded: bool) -> None:
        """Handle panel expansion change."""
        self._is_panel_open = expanded
        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if not expanded:
            self._last_device_id = None

    def _setup(self) -> None:
        """Setup UI structure."""
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

    def _clear_layout(self) -> None:
        """Clear existing layout items."""
        if not self._layout:
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _apply_theme_styles(self) -> None:
        """Apply theme styles using ThemeService tokens."""
        tokens = self._theme_service.tokens

        # Panel container
        self._container.setStyleSheet(
            f"""
            QFrame#right_slide_menu_frame {{
                background-color: {tokens.get_rgba("slide.bg", 0.98)};
                border: none;
                border-left: 1px solid {tokens.get_rgba("border", 0.5)};
            }}
        """
        )

        # Text styles
        self._title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {tokens.app_fg};")
        self._desc.setStyleSheet(f"font-size: 11px; color: {tokens.hint};")
        self._last_update.setStyleSheet(f"font-size: 11px; color: {tokens.hint};")

        # Card frames
        card_style = self._theme_service.get_card_style()
        self._mat_frame.setStyleSheet(f"QFrame#mat_frame {{ {card_style} }}")
        self._details_frame.setStyleSheet(f"QFrame#details_frame {{ {card_style} }}")

        self._batch.setStyleSheet(f"font-weight: 600; color: {tokens.app_fg};")
        self._fed_time.setStyleSheet(f"font-size: 10px; color: {tokens.hint};")

        # Labels
        self._lbl_oee.setStyleSheet(f"font-weight: 600; margin-top: 6px; color: {tokens.app_fg};")
        self._lbl_yield.setStyleSheet(f"font-weight: 600; margin-top: 4px; color: {tokens.app_fg};")

        # Progress bars
        bar_style = self._theme_service.get_progress_bar_style()
        self._bar_oee.setStyleSheet(bar_style)
        self._bar_yield.setStyleSheet(bar_style)

        # Detail labels
        for label in [self._inputs, self._outputs, self._cycle]:
            label.setStyleSheet(f"color: {tokens.app_fg};")

    def _render_device_from_model(self, device) -> None:
        """Render device from DeviceDisplayModel."""
        tokens = self._theme_service.tokens

        if hasattr(device, "device_id"):
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

            # OEE with dynamic color
            oee_val = float(device.oee) if device.oee else 0
            self._lbl_oee.setText(f"OEE: {oee_val:.1f}%")
            self._bar_oee.setValue(int(min(oee_val, 100)))

            if oee_val > 85:
                bar_color = tokens.success
            elif oee_val > 60:
                bar_color = tokens.warning
            else:
                bar_color = tokens.error

            self._bar_oee.setStyleSheet(self._theme_service.get_progress_bar_style(bar_color))

            # Yield
            yield_val = float(device.yield_rate) if device.yield_rate else 0
            self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
            self._bar_yield.setValue(int(min(yield_val, 100)))
            self._bar_yield.setStyleSheet(self._theme_service.get_progress_bar_style(tokens.accent))

            self._inputs.setText(f"📥 Inputs: {device.input_count:,}")
            self._outputs.setText(f"📦 Outputs: {device.output_count:,}")
            self._cycle.setText(f"⏱️ Cycle: {device.cycle_time}s")

            if device.last_error:
                self._error.setText(f"⚠️ {device.last_error}")
                self._error.setStyleSheet(f"color: {tokens.error}; font-weight: 600;")
            else:
                self._error.setText("✅ Healthy")
                self._error.setStyleSheet(f"color: {tokens.success};")
        else:
            self._render_device_info(device, device.get("device_id", "Unknown"))

    def _show_no_selection(self) -> None:
        """Show no device selected state."""
        tokens = self._theme_service.tokens

        self._title.setText("SELECT DEVICE")
        self._status_badge.setText("N/A")
        self._status_badge.setStyleSheet(
            f"background-color: {tokens.hint}; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;"
        )
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
        self._error.setStyleSheet(f"color: {tokens.hint};")

    def _show_loading_device(self, device_id: str) -> None:
        """Show loading state for selected device."""
        tokens = self._theme_service.tokens

        self._title.setText(device_id)
        self._status_badge.setText("LOADING")
        self._status_badge.setStyleSheet(
            f"background-color: {tokens.hint}; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;"
        )
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
        self._error.setStyleSheet(f"color: {tokens.hint};")

    def _render_device_info(self, device: Any, device_id: str) -> None:
        """Render device information from dict (legacy support)."""
        tokens = self._theme_service.tokens

        def get_val(key: str, default: Any = None) -> Any:
            if isinstance(device, dict):
                return device.get(key, default)
            return getattr(device, key, default)

        display_name = get_val("display_name") or get_val("equip_name") or device_id
        status_name = get_val("status_name") or "Unknown"
        status_color = get_val("status_color") or tokens.hint
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

        if oee_val > 85:
            bar_color = tokens.success
        elif oee_val > 60:
            bar_color = tokens.warning
        else:
            bar_color = tokens.error

        self._bar_oee.setStyleSheet(self._theme_service.get_progress_bar_style(bar_color))

        yield_val = float(yield_rate) if yield_rate else 0
        self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
        self._bar_yield.setValue(int(min(yield_val, 100)))
        self._bar_yield.setStyleSheet(self._theme_service.get_progress_bar_style(tokens.accent))

        self._inputs.setText(f"📥 Inputs: {input_count:,}")
        self._outputs.setText(f"📦 Outputs: {output_count:,}")
        self._cycle.setText(f"⏱️ Cycle: {cycle_time}s")

        if last_error:
            self._error.setText(f"⚠️ {last_error}")
            self._error.setStyleSheet(f"color: {tokens.error}; font-weight: 600;")
        else:
            self._error.setText("✅ Healthy")
            self._error.setStyleSheet(f"color: {tokens.success};")

    def render(self, state: Dict[str, Any]) -> None:
        """Render panel based on state (legacy compatibility)."""
        is_expanded = select_right_panel_expanded(state)

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
