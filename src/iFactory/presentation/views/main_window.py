# File: presentation/views/main_window.py
"""
Main Window - MVVM Architecture (Optimized).

Click-outside detection using focused approach instead of global event filter.
Uses ThemeService for centralized theming.
Uses IconService for icon management.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import QTimer, Slot, QPoint, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QMouseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

import iFactory.presentation.resources.resources_rc as resources_rc

sys.modules["resources_rc"] = resources_rc

from ..constants.layout import Layout
from ..constants.timing import Timing
from ..state.selectors import select_factory_summary
from .shell.header import HeaderView
from .shell.right_panel import RightPanelView
from .shell.sidebar import SidebarView
from .shell.status_bar import StatusBarView
from .ui.generated.main_ui import Ui_MainWindow
from .widgets.device_canvas import DeviceCanvasWidget
from .widgets.device_gantt_widget import DeviceGanttDisplayWidget
from .widgets.legend_widget import LegendWidget

if TYPE_CHECKING:
    from ..services.page_device_manager import PageDeviceManager
    from ..services.theme_service import ThemeService
    from ..state.store import Store
    from ..viewmodels import (
        DeviceListViewModel,
        GanttChartViewModel,
        ShellViewModel,
        GanttChartModel,
        DeviceSelectionModel,
    )

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window - PASSIVE VIEW.

    Optimized features:
    - Click-outside detection using mousePressEvent
    - Immediate response without timer delays
    - Clean separation of device clicks vs outside clicks
    - ThemeService for all theming needs
    - Consistent styling via design tokens
    """

    def __init__(
        self,
        store: "Store",
        shell_vm: "ShellViewModel",
        device_vm: "DeviceListViewModel",
        gantt_vm: "GanttChartViewModel",
        theme_service: "ThemeService",
        page_manager: Optional["PageDeviceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._store = store
        self._shell_vm = shell_vm
        self._device_vm = device_vm
        self._gantt_vm = gantt_vm
        self._theme_service = theme_service
        self._page_manager = page_manager

        self._prev_state: Dict[str, Any] = {}
        self._components_ready = False

        # Setup UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory Production Monitor")

        # Initialize
        self._apply_initial_layout()
        self._init_shell()

        # Deferred workspace initialization
        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._init_workspace)

        self._setup_shortcuts()
        self._bind_viewmodels()

        # Apply initial theme
        self._apply_theme(self._theme_service.current_theme)

        # Legacy store binding
        self._store.state_changed.connect(self._on_state_changed)

        logger.info("[MainWindow] Initialized with MVVM and ThemeService")

    # =========================================================================
    # Click-Outside Detection
    # =========================================================================

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press on MainWindow background."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._handle_background_click(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _handle_background_click(self, global_pos: QPoint) -> None:
        """Handle click on background area."""
        if not self._shell_vm.right_panel_expanded:
            return

        # Don't close if clicking inside right panel
        if self._is_point_in_widget(global_pos, self.ui.right_slide_menu_frame):
            return

        logger.debug("[MainWindow] Background click detected - closing panel")
        self._close_panel_only()

    def _is_point_in_widget(self, global_pos: QPoint, widget: Optional[QWidget]) -> bool:
        """Check if global point is inside widget bounds."""
        if not widget or not widget.isVisible():
            return False
        try:
            local_pos = widget.mapFromGlobal(global_pos)
            return widget.rect().contains(local_pos)
        except Exception:
            return False

    def _close_panel_only(self) -> None:
        """Close right panel without deselecting device."""
        self._shell_vm.close_right_panel()
        logger.info("[MainWindow] Panel closed (device still selected)")

    def _close_panel_and_deselect(self) -> None:
        """Close right panel and deselect device."""
        self._shell_vm.close_right_panel()
        self._device_vm.deselect_device()
        logger.info("[MainWindow] Panel closed and device deselected")

    # =========================================================================
    # ViewModel Bindings
    # =========================================================================

    def _bind_viewmodels(self) -> None:
        """Bind to ViewModel signals."""
        # Device ViewModel
        self._device_vm.devicesChanged.connect(self._on_devices_updated)
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._device_vm.stateChanged.connect(self._on_device_state_changed)

        # Gantt ViewModel
        self._gantt_vm.chartReady.connect(self._on_chart_ready)
        self._gantt_vm.loadingStateChanged.connect(self._on_gantt_loading_changed)

        # Shell ViewModel
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.pageChanged.connect(self._on_page_changed)
        self._shell_vm.sidebarChanged.connect(self._on_sidebar_changed)
        self._shell_vm.rightPanelChanged.connect(self._on_right_panel_changed)

    # =========================================================================
    # Device ViewModel Handlers
    # =========================================================================

    @Slot(dict)
    def _on_devices_updated(self, devices: Dict[str, Any]) -> None:
        if not self._components_ready:
            return

        logger.debug(f"[MainWindow] Devices updated: {len(devices)} devices")

        is_dark = self._theme_service.is_dark

        # Convert to dict if needed
        devices_dict = {}
        for code, device in devices.items():
            if hasattr(device, "to_dict"):
                devices_dict[code] = device.to_dict()
            else:
                devices_dict[code] = device

        self.canvas_dashboard.render_state(devices_dict, is_dark)
        self.canvas_orders.render_state(devices_dict, is_dark)

    @Slot(object)
    def _on_selection_changed(self, selection: "DeviceSelectionModel") -> None:
        if not self._components_ready:
            return

        if selection.has_selection:
            self._gantt_vm.load_device_chart(
                device_code=selection.selected_device_id,
                device_name=self._get_device_name(selection.selected_device_id),
            )
        else:
            self._gantt_vm.clear_chart()
            self.device_gantt_dashboard.show_placeholder()
            self.device_gantt_orders.show_placeholder()
            self.legend_dashboard.clear_stats()
            self.legend_orders.clear_stats()

    @Slot(object)
    def _on_device_state_changed(self, state) -> None:
        pass

    def _get_device_name(self, device_id: str) -> str:
        devices = self._device_vm.devices
        device = devices.get(device_id)
        if device:
            return device.display_name if hasattr(device, "display_name") else str(device)
        return device_id

    # =========================================================================
    # Gantt ViewModel Handlers
    # =========================================================================

    @Slot(object)
    def _on_chart_ready(self, chart: "GanttChartModel") -> None:
        if not self._components_ready:
            return

        logger.info(f"[MainWindow] Chart ready: {chart.device_code}")

        segments = [
            {
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "status_code": seg.status_code,
                "status_name": seg.status_name,
                "duration_seconds": seg.duration_seconds,
            }
            for seg in chart.segments
        ]

        # Update both gantt widgets
        self.device_gantt_dashboard.render_device_gantt(
            device_code=chart.device_code,
            device_name=chart.device_name,
            segments=segments,
            start_time=chart.start_time,
            end_time=chart.end_time,
        )
        self.device_gantt_orders.render_device_gantt(
            device_code=chart.device_code,
            device_name=chart.device_name,
            segments=segments,
            start_time=chart.start_time,
            end_time=chart.end_time,
        )

        # Update legends
        gantt_data = {chart.device_code: segments}
        self.legend_dashboard.render_stats(gantt_data, chart.start_time, chart.end_time)
        self.legend_orders.render_stats(gantt_data, chart.start_time, chart.end_time)

    @Slot(object)
    def _on_gantt_loading_changed(self, state) -> None:
        if state.is_loading and self._components_ready:
            now = datetime.now()
            start = now - timedelta(hours=24)

            self.device_gantt_dashboard.render_device_gantt(
                device_code=state.device_code,
                device_name=f"{state.device_code} (Loading...)",
                segments=[],
                start_time=start,
                end_time=now,
            )
            self.device_gantt_orders.render_device_gantt(
                device_code=state.device_code,
                device_name=f"{state.device_code} (Loading...)",
                segments=[],
                start_time=start,
                end_time=now,
            )

    # =========================================================================
    # Shell ViewModel Handlers
    # =========================================================================

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme(theme)

    @Slot(str)
    def _on_page_changed(self, page: str) -> None:
        self._switch_page(page)

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        width = Layout.SIDEBAR_EXPANDED_WIDTH if expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self.ui.left_slide_menu_frame.setFixedWidth(width)
        self.ui.title_frame.setFixedWidth(width)

    @Slot(bool)
    def _on_right_panel_changed(self, expanded: bool) -> None:
        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self.ui.right_slide_menu_frame.setFixedWidth(width)
        logger.info(f"[MainWindow] Right panel changed: expanded={expanded}, width={width}")

    # =========================================================================
    # Canvas Event Handlers
    # =========================================================================

    def _on_device_single_clicked(self, device_id: str) -> None:
        """Handle single click on device."""
        logger.info(f"[MainWindow] Device single clicked: {device_id}")
        self._device_vm.select_device(device_id, open_panel=False)

    def _on_device_double_clicked(self, device_id: str) -> None:
        """Handle double click on device."""
        logger.info(f"[MainWindow] Device double clicked: {device_id}")
        self._device_vm.select_device(device_id, open_panel=True)

    # =========================================================================
    # Keyboard Shortcuts
    # =========================================================================

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._shell_vm.toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._shell_vm.toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._shell_vm.toggle_right_panel)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape_pressed)

    def _on_escape_pressed(self) -> None:
        """Handle Escape key."""
        if self._shell_vm.right_panel_expanded:
            self._shell_vm.close_right_panel()
        self._device_vm.deselect_device()

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _apply_initial_layout(self) -> None:
        """Apply initial layout dimensions."""
        self.ui.right_slide_menu_frame.setFixedWidth(Layout.RIGHT_PANEL_COLLAPSED_WIDTH)
        self.ui.left_slide_menu_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)

        # Set initial page
        if hasattr(self.ui, "dashboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.dashboard_page)
        elif hasattr(self.ui, "daboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.daboard_page)

    def _init_shell(self) -> None:
        """Initialize shell components with ThemeService."""
        self.header = HeaderView(
            container=self.ui.title_frame,
            toggle_btn=getattr(self.ui, "pushButton", None),
            title_label=getattr(self.ui, "title_label", None),
            title_icon=getattr(self.ui, "title_icon", None),
            window_buttons=(
                getattr(self.ui, "minimize_window_button", None),
                getattr(self.ui, "restore_window_button", None),
                getattr(self.ui, "close_window_button", None),
            ),
            shell_vm=self._shell_vm,
            theme_service=self._theme_service,
        )

        self.sidebar = SidebarView(
            container=self.ui.left_slide_menu_frame,
            nav_list=self.ui.listWidget,
            settings_list=self.ui.listWidget_settings,
            shell_vm=self._shell_vm,
            theme_service=self._theme_service,
        )

        self.right_panel = RightPanelView(
            container=self.ui.right_slide_menu_frame,
            store=self._store,
            device_vm=self._device_vm,
            shell_vm=self._shell_vm,
            theme_service=self._theme_service,
        )

        self.status_bar = StatusBarView(
            status_bar=self.ui.statusbar,
            shell_vm=self._shell_vm,
            theme_service=self._theme_service,
        )

    def _init_workspace(self) -> None:
        """Initialize workspace widgets (deferred)."""
        logger.info("[MainWindow] Initializing workspace...")

        try:
            dash_config = self._shell_vm.get_layout_config("daboard_midle_frame_1")
            orders_config = self._shell_vm.get_layout_config("orders_midle_frame_1")

            # Dashboard page widgets - inject ThemeService
            self.canvas_dashboard = self._embed(
                self.ui.daboard_midle_frame_1,
                DeviceCanvasWidget(
                    area_key="dashboard",
                    layout_config=dash_config,
                    theme_service=self._theme_service,
                    parent=self,
                ),
            )
            self.device_gantt_dashboard = self._embed(
                self.ui.daboard_midle_frame_2,
                DeviceGanttDisplayWidget(theme_service=self._theme_service, parent=self),  # NEW
            )
            self.legend_dashboard = self._embed(
                self.ui.daboard_bottom_frame,
                LegendWidget(theme_service=self._theme_service, parent=self),  # NEW
            )

            # Orders page widgets - inject ThemeService
            self.canvas_orders = self._embed(
                self.ui.orders_midle_frame_1,
                DeviceCanvasWidget(
                    area_key="orders",
                    layout_config=orders_config,
                    theme_service=self._theme_service,
                    parent=self,
                ),
            )
            self.device_gantt_orders = self._embed(
                self.ui.orders_midle_frame_2,
                DeviceGanttDisplayWidget(theme_service=self._theme_service, parent=self),  # NEW
            )
            self.legend_orders = self._embed(
                self.ui.orders_bottom_frame,
                LegendWidget(theme_service=self._theme_service, parent=self),  # NEW
            )

            # Connect canvas signals
            self.canvas_dashboard.device_clicked.connect(self._on_device_single_clicked)
            self.canvas_orders.device_clicked.connect(self._on_device_single_clicked)
            self.canvas_dashboard.device_double_clicked.connect(self._on_device_double_clicked)
            self.canvas_orders.device_double_clicked.connect(self._on_device_double_clicked)

            # Apply constraints
            self.ui.daboard_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)
            self.ui.orders_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)

            self._components_ready = True

            # Initial render
            devices = self._device_vm.devices
            if devices:
                is_dark = self._theme_service.is_dark
                devices_dict = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in devices.items()}
                self.canvas_dashboard.render_state(devices_dict, is_dark)
                self.canvas_orders.render_state(devices_dict, is_dark)

            # Show placeholders
            self.device_gantt_dashboard.show_placeholder()
            self.device_gantt_orders.show_placeholder()

            logger.info("[MainWindow] Workspace initialized")

        except Exception as e:
            logger.error(f"[MainWindow] Workspace init failed: {e}", exc_info=True)

    def _embed(self, parent: QWidget, widget: QWidget) -> QWidget:
        """Embed widget into parent container."""
        layout = parent.layout()
        if not layout:
            layout = QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        layout.addWidget(widget)
        return widget

    # =========================================================================
    # Theme Application
    # =========================================================================

    def _apply_theme(self, theme: str) -> None:
        """Apply theme using ThemeService."""
        self._theme_service.set_theme(theme)

        # Apply global stylesheet
        stylesheet = self._theme_service.get_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)
            self.style().unpolish(self)
            self.style().polish(self)

        # Apply page-specific styles
        self._apply_page_theme()

        # Update widgets that need explicit theme update
        if self._components_ready:
            is_dark = self._theme_service.is_dark
            self.device_gantt_dashboard.set_theme(is_dark)
            self.device_gantt_orders.set_theme(is_dark)

    def _apply_page_theme(self) -> None:
        """Apply page theme using ThemeService tokens."""
        tokens = self._theme_service.tokens

        # Page backgrounds
        page_style = f"background-color: {tokens.surface_app};"
        for page_name in ["daboard_page", "orders_page"]:
            page = getattr(self.ui, page_name, None)
            if page:
                page.setStyleSheet(page_style)

        # Top frames
        top_frame_style = f"""
            QFrame {{
                background-color: {tokens.surface_card};
                border: none;
                border-bottom: 1px solid {tokens.border_default};
            }}
        """
        for frame_name in ["daboard_top_frame", "orders_top_frame"]:
            frame = getattr(self.ui, frame_name, None)
            if frame:
                frame.setStyleSheet(top_frame_style)

        # Bottom frames
        bottom_frame_style = f"""
            QFrame {{
                background-color: {tokens.surface_card};
                border: none;
                border-top: 1px solid {tokens.border_default};
            }}
        """
        for frame_name in ["daboard_bottom_frame", "orders_bottom_frame"]:
            frame = getattr(self.ui, frame_name, None)
            if frame:
                frame.setStyleSheet(bottom_frame_style)

    def _switch_page(self, page: str) -> None:
        """Switch to specified page."""
        # Handle legacy naming
        page_name = page.replace("dashboard", "daboard") if "dashboard" in page else page
        target = getattr(self.ui, page_name, None)
        if target and self.ui.stackedWidget.currentWidget() != target:
            self.ui.stackedWidget.setCurrentWidget(target)

    def _update_lcd_displays(self, state: Dict[str, Any]) -> None:
        """Update LCD displays with factory summary."""
        summary = select_factory_summary(state)
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("total_output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        """Handle store state changes (for shell components - legacy)."""
        self.sidebar.render(state)
        self.header.render(state)
        self.right_panel.render(state)
        self.status_bar.render(state)
        self._update_lcd_displays(state)
        self._prev_state = state.copy()


__all__ = ["MainWindow"]
