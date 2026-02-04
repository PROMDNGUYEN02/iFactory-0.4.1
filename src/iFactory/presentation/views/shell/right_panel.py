# File: presentation/views/shell/right_panel.py
"""
Right Panel - Device details view.

OPTIMIZED:
- Cached style strings per theme
- Skip redundant renders
- Lazy style computation

FEATURES:
- Availability display with progress bar
- Material Inputs list display (NEW)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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
    from ...viewmodels.models.device_model import MaterialInputModel

logger = logging.getLogger(__name__)


class MaterialInputWidget(QFrame):
    """
    Widget to display a single material input.

    Shows:
    - Material batch
    - Material name (truncated)
    - Feed time
    """

    def __init__(
        self,
        material: "MaterialInputModel",
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._material = material
        self._theme_service = theme_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        tokens = self._theme_service.tokens

        self.setObjectName("material_item")
        self.setStyleSheet(
            f"""
            QFrame#material_item {{
                background-color: {tokens.get_rgba("card.bg", 0.6)};
                border: 1px solid {tokens.get_rgba("border", 0.3)};
                border-radius: 6px;
                padding: 6px;
                margin: 2px 0;
            }}
            QFrame#material_item:hover {{
                background-color: {tokens.get_rgba("card.bg", 0.9)};
                border-color: {tokens.accent};
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Batch label (bold, primary)
        self._batch_label = QLabel(f"📦 {self._material.material_batch}")
        self._batch_label.setStyleSheet(
            f"""
            font-weight: 600;
            font-size: 11px;
            color: {tokens.app_fg};
        """
        )
        layout.addWidget(self._batch_label)

        # Material name (smaller, hint color)
        name_display = self._material.display_name
        self._name_label = QLabel(name_display)
        self._name_label.setStyleSheet(
            f"""
            font-size: 10px;
            color: {tokens.hint};
        """
        )
        self._name_label.setWordWrap(True)
        self._name_label.setToolTip(self._material.material_name)  # Full name on hover
        layout.addWidget(self._name_label)

        # Feed time (smallest)
        self._time_label = QLabel(f"⏰ {self._material.formatted_time}")
        self._time_label.setStyleSheet(
            f"""
            font-size: 9px;
            color: {tokens.hint};
        """
        )
        layout.addWidget(self._time_label)


class RightPanelView:
    """
    Right panel showing device details.

    OPTIMIZED:
    - Cached styles per theme
    - Skip redundant renders

    FEATURES:
    - Availability display below OEE
    - Material Inputs list (scrollable)
    """

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
        self._current_theme = theme_service.current_theme
        self._cached_styles: Dict[str, Dict[str, str]] = {}

        self._layout: Optional[QVBoxLayout] = None
        self._material_widgets: List[MaterialInputWidget] = []

        self._setup()
        self._apply_theme_styles()
        self._bind_viewmodels()

    def _bind_viewmodels(self) -> None:
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._device_vm.materialInputsChanged.connect(self._on_material_inputs_changed)
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.rightPanelChanged.connect(self._on_panel_changed)

    @Slot(object)
    def _on_selection_changed(self, selection) -> None:
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

    @Slot(str, list)
    def _on_material_inputs_changed(self, device_id: str, materials: List) -> None:
        """Handle material inputs update."""
        if device_id != self._last_device_id:
            return

        # Re-render the materials section
        device = self._device_vm.selected_device
        if device:
            self._render_material_inputs(device.material_inputs, device.current_lot_no)
            logger.debug(f"[RightPanelView] Material inputs updated: {len(materials)} items")

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change - OPTIMIZED."""
        if theme == self._current_theme:
            return

        self._current_theme = theme
        self._apply_theme_styles()

        # Re-render material widgets with new theme
        device = self._device_vm.selected_device
        if device and device.has_material_inputs:
            self._render_material_inputs(device.material_inputs, device.current_lot_no)

    @Slot(bool)
    def _on_panel_changed(self, expanded: bool) -> None:
        self._is_panel_open = expanded
        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if not expanded:
            self._last_device_id = None

    def _setup(self) -> None:
        if not self._container:
            return

        self._layout = self._container.layout()
        if not self._layout:
            self._layout = QVBoxLayout(self._container)

        self._clear_layout()
        self._layout.setContentsMargins(16, 20, 16, 20)
        self._layout.setSpacing(12)

        # Header with title and status badge
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

        # Last update time
        self._last_update = QLabel("Last Update: --")
        self._last_update.setObjectName("last_update")
        self._layout.addWidget(self._last_update)

        # ================================================================
        # Material Inputs Section - NEW
        # ================================================================
        self._mat_section_label = QLabel("📥 Material Inputs")
        self._mat_section_label.setObjectName("section_label")
        self._layout.addWidget(self._mat_section_label)

        # LOT NO label
        self._lot_label = QLabel("LOT: --")
        self._lot_label.setObjectName("lot_label")
        self._layout.addWidget(self._lot_label)

        # Scrollable area for material inputs
        self._mat_scroll = QScrollArea()
        self._mat_scroll.setObjectName("mat_scroll")
        self._mat_scroll.setWidgetResizable(True)
        self._mat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._mat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._mat_scroll.setMaximumHeight(150)  # Limit height
        self._mat_scroll.setMinimumHeight(60)

        self._mat_container = QWidget()
        self._mat_container_layout = QVBoxLayout(self._mat_container)
        self._mat_container_layout.setContentsMargins(0, 0, 0, 0)
        self._mat_container_layout.setSpacing(4)
        self._mat_container_layout.addStretch()

        self._mat_scroll.setWidget(self._mat_container)
        self._layout.addWidget(self._mat_scroll)

        # No materials placeholder
        self._no_mat_label = QLabel("No materials loaded")
        self._no_mat_label.setObjectName("no_mat_label")
        self._no_mat_label.setAlignment(Qt.AlignCenter)
        self._mat_container_layout.insertWidget(0, self._no_mat_label)
        # ================================================================

        # OEE
        self._lbl_oee = QLabel("OEE: 0%")
        self._bar_oee = QProgressBar()
        self._bar_oee.setTextVisible(False)
        self._bar_oee.setFixedHeight(8)
        self._layout.addWidget(self._lbl_oee)
        self._layout.addWidget(self._bar_oee)

        # ================================================================
        # Availability Section
        # ================================================================
        self._lbl_availability = QLabel("Availability: 0%")
        self._lbl_availability.setObjectName("lbl_availability")
        self._bar_availability = QProgressBar()
        self._bar_availability.setTextVisible(False)
        self._bar_availability.setFixedHeight(8)
        self._bar_availability.setObjectName("bar_availability")
        self._lbl_run_time = QLabel("⏱️ Run: 00:00:00 / Total: 00:00:00")
        self._lbl_run_time.setObjectName("lbl_run_time")
        self._layout.addWidget(self._lbl_availability)
        self._layout.addWidget(self._bar_availability)
        self._layout.addWidget(self._lbl_run_time)
        # ================================================================

        # Yield Rate
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

        # Error status
        self._error = QLabel("Last Error: None")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

        self._layout.addStretch()

    def _clear_layout(self) -> None:
        if not self._layout:
            return
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_material_widgets(self) -> None:
        """Clear all material input widgets."""
        for widget in self._material_widgets:
            try:
                widget.deleteLater()
            except RuntimeError:
                pass
        self._material_widgets.clear()

    def _get_cached_styles(self) -> Dict[str, str]:
        """Get or compute cached styles for current theme."""
        if self._current_theme in self._cached_styles:
            return self._cached_styles[self._current_theme]

        tokens = self._theme_service.tokens
        card_style = self._theme_service.get_card_style()
        bar_style = self._theme_service.get_progress_bar_style()

        styles = {
            "container": f"""
                QFrame#right_slide_menu_frame {{
                    background-color: {tokens.get_rgba("slide.bg", 0.98)};
                    border: none;
                    border-left: 1px solid {tokens.get_rgba("border", 0.5)};
                }}
            """,
            "title": f"font-size: 14px; font-weight: 700; color: {tokens.app_fg};",
            "desc": f"font-size: 11px; color: {tokens.hint};",
            "last_update": f"font-size: 11px; color: {tokens.hint};",
            "card_frame": f"QFrame {{ {card_style} }}",
            "section_label": f"font-weight: 700; font-size: 12px; color: {tokens.app_fg}; margin-top: 8px;",
            "lot_label": f"font-size: 11px; font-weight: 600; color: {tokens.accent};",
            "no_mat_label": f"font-size: 10px; color: {tokens.hint}; font-style: italic;",
            "mat_scroll": f"""
                QScrollArea#mat_scroll {{
                    background-color: transparent;
                    border: 1px solid {tokens.get_rgba("border", 0.3)};
                    border-radius: 6px;
                }}
                QScrollArea#mat_scroll > QWidget > QWidget {{
                    background-color: transparent;
                }}
            """,
            "lbl_oee": f"font-weight: 600; margin-top: 6px; color: {tokens.app_fg};",
            "lbl_availability": f"font-weight: 600; margin-top: 6px; color: {tokens.app_fg};",
            "lbl_run_time": f"font-size: 10px; color: {tokens.hint}; margin-bottom: 4px;",
            "lbl_yield": f"font-weight: 600; margin-top: 4px; color: {tokens.app_fg};",
            "bar_style": bar_style,
            "detail_label": f"color: {tokens.app_fg};",
        }

        self._cached_styles[self._current_theme] = styles
        return styles

    def _apply_theme_styles(self) -> None:
        """Apply theme styles - CACHED."""
        styles = self._get_cached_styles()

        self._container.setStyleSheet(styles["container"])
        self._title.setStyleSheet(styles["title"])
        self._desc.setStyleSheet(styles["desc"])
        self._last_update.setStyleSheet(styles["last_update"])

        # Material section styles
        self._mat_section_label.setStyleSheet(styles["section_label"])
        self._lot_label.setStyleSheet(styles["lot_label"])
        self._no_mat_label.setStyleSheet(styles["no_mat_label"])
        self._mat_scroll.setStyleSheet(styles["mat_scroll"])

        self._details_frame.setStyleSheet(styles["card_frame"].replace("QFrame", "QFrame#details_frame"))
        self._lbl_oee.setStyleSheet(styles["lbl_oee"])
        self._lbl_availability.setStyleSheet(styles["lbl_availability"])
        self._lbl_run_time.setStyleSheet(styles["lbl_run_time"])
        self._lbl_yield.setStyleSheet(styles["lbl_yield"])
        self._bar_oee.setStyleSheet(styles["bar_style"])
        self._bar_availability.setStyleSheet(styles["bar_style"])
        self._bar_yield.setStyleSheet(styles["bar_style"])

        for label in [self._inputs, self._outputs, self._cycle]:
            label.setStyleSheet(styles["detail_label"])

    def _format_run_time(self, seconds: float) -> str:
        """Format run time seconds to HH:MM:SS."""
        total_seconds = int(max(0, seconds))  # Ensure non-negative
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _render_material_inputs(
        self,
        materials: tuple,
        lot_no: str = "",
    ) -> None:
        """Render material inputs in the scrollable area."""
        # Clear existing widgets
        self._clear_material_widgets()

        # Update LOT label
        if lot_no:
            self._lot_label.setText(f"🏷️ LOT: {lot_no}")
            self._lot_label.setVisible(True)
        else:
            self._lot_label.setText("LOT: --")

        # Show/hide no materials label
        has_materials = len(materials) > 0
        self._no_mat_label.setVisible(not has_materials)

        if not has_materials:
            return

        # Create widgets for each material
        for material in materials:
            widget = MaterialInputWidget(
                material=material,
                theme_service=self._theme_service,
                parent=self._mat_container,
            )
            # Insert before the stretch
            self._mat_container_layout.insertWidget(
                self._mat_container_layout.count() - 1,
                widget,
            )
            self._material_widgets.append(widget)

        logger.debug(f"[RightPanelView] Rendered {len(materials)} material inputs")

    def _render_device_from_model(self, device) -> None:
        """Render device information from DeviceDisplayModel."""
        tokens = self._theme_service.tokens

        if hasattr(device, "device_id"):
            # Title and description
            self._title.setText(str(device.display_name))
            self._desc.setText(str(device.description) if device.description else "")
            self._desc.setVisible(bool(device.description))

            # Last update
            if device.last_update:
                clean_time = str(device.last_update).replace("T", " ").split(".")[0]
                self._last_update.setText(f"🕒 {clean_time}")
            else:
                self._last_update.setText("🕒 --")

            # Status badge
            self._status_badge.setText(str(device.status_name).upper())
            self._status_badge.setStyleSheet(
                f"background-color: {device.status_color}; color: white; font-weight: 600; "
                f"padding: 4px 12px; border-radius: 10px; font-size: 10px;"
            )

            # ================================================================
            # Material Inputs - NEW
            # ================================================================
            self._render_material_inputs(
                device.material_inputs,
                device.current_lot_no,
            )
            # ================================================================

            # OEE
            oee_val = float(device.oee) if device.oee else 0
            self._lbl_oee.setText(f"OEE: {oee_val:.1f}%")
            self._bar_oee.setValue(int(min(oee_val, 100)))

            if oee_val > 85:
                oee_bar_color = tokens.success
            elif oee_val > 60:
                oee_bar_color = tokens.warning
            else:
                oee_bar_color = tokens.error

            self._bar_oee.setStyleSheet(self._theme_service.get_progress_bar_style(oee_bar_color))

            # ================================================================
            # Availability
            # ================================================================
            availability_val = float(device.availability) if hasattr(device, "availability") else 0.0
            run_time_seconds = float(device.run_time_seconds) if hasattr(device, "run_time_seconds") else 0.0
            total_time_seconds = float(device.total_time_seconds) if hasattr(device, "total_time_seconds") else 0.0

            self._lbl_availability.setText(f"📊 Availability: {availability_val:.1f}%")
            self._bar_availability.setValue(int(min(availability_val, 100)))

            # Format run time and total time as HH:MM:SS
            run_time_str = self._format_run_time(run_time_seconds)
            total_time_str = self._format_run_time(total_time_seconds)
            self._lbl_run_time.setText(f"⏱️ Run: {run_time_str} / Total: {total_time_str}")

            # Color coding for availability bar
            if availability_val > 80:
                avail_bar_color = tokens.success
            elif availability_val > 50:
                avail_bar_color = tokens.warning
            else:
                avail_bar_color = tokens.error

            self._bar_availability.setStyleSheet(self._theme_service.get_progress_bar_style(avail_bar_color))
            # ================================================================

            # Yield Rate
            yield_val = float(device.yield_rate) if device.yield_rate else 0
            self._lbl_yield.setText(f"Yield: {yield_val:.1f}%")
            self._bar_yield.setValue(int(min(yield_val, 100)))
            self._bar_yield.setStyleSheet(self._theme_service.get_progress_bar_style(tokens.accent))

            # Details
            self._inputs.setText(f"📥 Inputs: {device.input_count:,}")
            self._outputs.setText(f"📦 Outputs: {device.output_count:,}")
            self._cycle.setText(f"⏱️ Cycle: {device.cycle_time}s")

            # Error status
            if device.last_error:
                self._error.setText(f"⚠️ {device.last_error}")
                self._error.setStyleSheet(f"color: {tokens.error}; font-weight: 600;")
            else:
                self._error.setText("✅ Healthy")
                self._error.setStyleSheet(f"color: {tokens.success};")
        else:
            # Fallback to dict-based rendering
            self._render_device_info(device, device.get("device_id", "Unknown"))

    def _show_no_selection(self) -> None:
        """Show default state when no device is selected."""
        tokens = self._theme_service.tokens

        self._title.setText("SELECT DEVICE")
        self._status_badge.setText("N/A")
        self._status_badge.setStyleSheet(
            f"background-color: {tokens.hint}; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;"
        )
        self._desc.setText("")
        self._desc.setVisible(False)
        self._last_update.setText("🕒 --")

        # Material inputs
        self._lot_label.setText("LOT: --")
        self._clear_material_widgets()
        self._no_mat_label.setVisible(True)

        self._lbl_oee.setText("OEE: 0%")
        self._bar_oee.setValue(0)

        # Availability
        self._lbl_availability.setText("📊 Availability: 0%")
        self._bar_availability.setValue(0)
        self._lbl_run_time.setText("⏱️ Run: 00:00:00 / Total: 00:00:00")

        self._lbl_yield.setText("Yield: 0%")
        self._bar_yield.setValue(0)
        self._inputs.setText("📥 Inputs: 0")
        self._outputs.setText("📦 Outputs: 0")
        self._cycle.setText("⏱️ Cycle: 0s")
        self._error.setText("--")
        self._error.setStyleSheet(f"color: {tokens.hint};")

    def _show_loading_device(self, device_id: str) -> None:
        """Show loading state for a device."""
        tokens = self._theme_service.tokens

        self._title.setText(device_id)
        self._status_badge.setText("LOADING")
        self._status_badge.setStyleSheet(
            f"background-color: {tokens.hint}; color: white; padding: 4px 10px; " "border-radius: 10px; font-size: 10px;"
        )
        self._desc.setText("Loading device data...")
        self._desc.setVisible(True)
        self._last_update.setText("🕒 --")

        # Material inputs loading
        self._lot_label.setText("LOT: Loading...")
        self._clear_material_widgets()
        self._no_mat_label.setText("Loading materials...")
        self._no_mat_label.setVisible(True)

        self._lbl_oee.setText("OEE: --%")
        self._bar_oee.setValue(0)

        # Availability
        self._lbl_availability.setText("📊 Availability: --%")
        self._bar_availability.setValue(0)
        self._lbl_run_time.setText("⏱️ Run: --:--:-- / Total: --:--:--")

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
        oee = get_val("oee") or 0
        yield_rate = get_val("yield_rate") or 0
        input_count = get_val("input_count") or 0
        output_count = get_val("output_count") or 0
        cycle_time = get_val("cycle_time") or 0
        last_error = get_val("last_error")

        # Availability
        availability = get_val("availability") or 0
        run_time_seconds = get_val("run_time_seconds") or 0
        total_time_seconds = get_val("total_time_seconds") or 0

        # Material inputs
        material_inputs = get_val("material_inputs") or []
        current_lot_no = get_val("current_lot_no") or ""

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

        # Material inputs (from dict)
        if material_inputs:
            from ...viewmodels.models.device_model import MaterialInputModel

            mats = []
            for m in material_inputs:
                if isinstance(m, dict):
                    mats.append(MaterialInputModel.from_dict(m))
                else:
                    mats.append(m)
            self._render_material_inputs(tuple(mats), current_lot_no)
        else:
            self._lot_label.setText("LOT: --")
            self._clear_material_widgets()
            self._no_mat_label.setText("No materials loaded")
            self._no_mat_label.setVisible(True)

        # OEE
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

        # Availability
        availability_val = float(availability) if availability else 0
        run_time_val = float(run_time_seconds) if run_time_seconds else 0
        total_time_val = float(total_time_seconds) if total_time_seconds else 0

        self._lbl_availability.setText(f"📊 Availability: {availability_val:.1f}%")
        self._bar_availability.setValue(int(min(availability_val, 100)))

        run_time_str = self._format_run_time(run_time_val)
        total_time_str = self._format_run_time(total_time_val)
        self._lbl_run_time.setText(f"⏱️ Run: {run_time_str} / Total: {total_time_str}")

        if availability_val > 80:
            avail_bar_color = tokens.success
        elif availability_val > 50:
            avail_bar_color = tokens.warning
        else:
            avail_bar_color = tokens.error

        self._bar_availability.setStyleSheet(self._theme_service.get_progress_bar_style(avail_bar_color))

        # Yield
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


__all__ = ["RightPanelView", "MaterialInputWidget"]
