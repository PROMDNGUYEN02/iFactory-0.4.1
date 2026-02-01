"""
Main Window - MVVM Architecture.

The View is a passive consumer that:
- Binds to ViewModel signals
- Delegates all user interactions to ViewModels
- Contains no business logic
- Handles click-outside detection for panels using eventFilter
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import QEvent, QRect, QTimer, Slot, QPoint, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

import iFactory.presentation.resources.resources_rc as resources_rc

sys.modules["resources_rc"] = resources_rc

from ..constants.layout import Layout
from ..constants.timing import Timing
from ..resources.themes import get_theme_manager
from ..state.selectors import (
    select_current_page,
    select_devices,
    select_factory_summary,
    select_right_panel_expanded,
    select_selected_device_id,
    select_sidebar_expanded,
    select_theme,
)
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

    Binds to ViewModel signals for state updates.
    Delegates user actions to ViewModels.
    Contains no business logic.
    Uses eventFilter for click-outside detection.

    Click-outside behavior:
    - Click on device widget → update panel content (handled by device click signals)
    - Click inside right panel → do nothing (allow interaction)
    - Click ANYWHERE else (stack widget, pages, frames, etc.) → CLOSE panel
    """

    def __init__(
        self,
        store: "Store",
        shell_vm: "ShellViewModel",
        device_vm: "DeviceListViewModel",
        gantt_vm: "GanttChartViewModel",
        page_manager: Optional["PageDeviceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._store = store
        self._shell_vm = shell_vm
        self._device_vm = device_vm
        self._gantt_vm = gantt_vm
        self._page_manager = page_manager
        self._theme_manager = get_theme_manager()

        self._prev_state: Dict[str, Any] = {}
        self._components_ready = False

        # Click handling - track if a device was just clicked
        self._device_click_pending = False

        # Store pending click position for deferred processing
        self._pending_click_pos: Optional[QPoint] = None

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory Production Monitor")

        self._apply_initial_layout()
        self._init_shell()

        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._init_workspace)

        self._setup_shortcuts()
        self._bind_viewmodels()
        self._apply_theme("light")

        self._store.state_changed.connect(self._on_state_changed)

        # Install event filter on QApplication to catch ALL mouse events
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
            logger.info("[MainWindow] Event filter installed on QApplication")

        logger.info("[MainWindow] Initialized with MVVM")

    # =========================================================================
    # Event Filter for Click-Outside Detection
    # =========================================================================

    def eventFilter(self, watched, event) -> bool:
        """
        Global event filter to detect clicks outside the right panel.

        Logic:
        - Capture click position immediately (before event is invalidated)
        - Defer processing to allow device signals to fire first
        - If device click pending → skip closing
        - If click inside right panel → skip closing
        - All other clicks → close panel
        """
        if event.type() == QEvent.Type.MouseButtonPress:
            # Only handle left clicks
            if hasattr(event, "button") and event.button() == Qt.MouseButton.LeftButton:
                # Capture position NOW before event is invalidated
                try:
                    if hasattr(event, "globalPosition"):
                        global_pos = event.globalPosition().toPoint()
                    elif hasattr(event, "globalPos"):
                        global_pos = event.globalPos()
                    else:
                        return False

                    # Store position and defer processing
                    self._pending_click_pos = QPoint(global_pos)
                    QTimer.singleShot(10, self._handle_global_click_deferred)

                except Exception as e:
                    logger.debug(f"[MainWindow] Error capturing click position: {e}")

        return False  # Never consume the event

    def _handle_global_click_deferred(self) -> None:
        """Handle global mouse click after device signals have processed."""
        global_pos = self._pending_click_pos
        self._pending_click_pos = None

        if global_pos is None:
            return

        # Check if a device click just happened
        if self._device_click_pending:
            self._device_click_pending = False
            logger.debug("[MainWindow] Click ignored - device click was processed")
            return

        # Check if right panel is open
        if not self._shell_vm.right_panel_expanded:
            logger.debug("[MainWindow] Panel not expanded - ignoring click")
            return

        # ONLY exclude: Right panel
        # Everything else (stack widget, pages, frames, canvas empty space, etc.) should close the panel

        # Check if click is inside right panel → allow interaction
        right_panel_rect = self._get_widget_global_rect(self.ui.right_slide_menu_frame)
        if right_panel_rect.isValid() and right_panel_rect.contains(global_pos):
            logger.debug("[MainWindow] Click inside right panel - ignoring")
            return

        # ALL OTHER CLICKS → close panel
        logger.info(f"[MainWindow] Click outside detected at {global_pos} - closing panel")
        self._close_panel_and_deselect()

    def _get_widget_global_rect(self, widget: Optional[QWidget]) -> QRect:
        """Get widget's global rectangle."""
        if not widget:
            return QRect()

        try:
            if not widget.isVisible():
                return QRect()

            top_left = widget.mapToGlobal(QPoint(0, 0))
            return QRect(top_left, widget.size())
        except Exception as e:
            logger.debug(f"[MainWindow] Error getting widget rect: {e}")
            return QRect()

    def _close_panel_and_deselect(self) -> None:
        """Close right panel and deselect device."""
        self._shell_vm.close_right_panel()
        self._device_vm.deselect_device()
        logger.info("[MainWindow] Panel closed and device deselected")

    def _mark_device_clicked(self) -> None:
        """Mark that a device was just clicked (to ignore click-outside)."""
        self._device_click_pending = True
        logger.debug("[MainWindow] Device click marked as pending")

    # =========================================================================
    # ViewModel Bindings
    # =========================================================================

    def _bind_viewmodels(self) -> None:
        """Bind to ViewModel signals."""
        self._device_vm.devicesChanged.connect(self._on_devices_updated)
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._device_vm.stateChanged.connect(self._on_device_state_changed)

        self._gantt_vm.chartReady.connect(self._on_chart_ready)
        self._gantt_vm.loadingStateChanged.connect(self._on_gantt_loading_changed)

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

        is_dark = self._theme_manager.is_dark

        # Convert DeviceDisplayModel to dict if needed
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
    # Canvas Event Handlers (User Interactions -> ViewModel)
    # =========================================================================

    def _on_device_single_clicked(self, device_id: str) -> None:
        """Handle single click on device - select device, update panel content."""
        logger.info(f"[MainWindow] Device single clicked: {device_id}")

        # Mark device click to prevent immediate click-outside closing panel
        self._mark_device_clicked()

        # Select device - this will update panel content if different device
        self._device_vm.select_device(device_id, open_panel=False)

    def _on_device_double_clicked(self, device_id: str) -> None:
        """Handle double click on device - select device and toggle panel."""
        logger.info(f"[MainWindow] Device double clicked: {device_id}")

        # Mark device click to prevent immediate click-outside closing panel
        self._mark_device_clicked()

        # Double click opens/toggles panel
        self._device_vm.select_device(device_id, open_panel=True)

    # =========================================================================
    # Keyboard Shortcuts
    # =========================================================================

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._shell_vm.toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._shell_vm.toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._shell_vm.toggle_right_panel)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape_pressed)

    def _on_escape_pressed(self) -> None:
        if self._shell_vm.right_panel_expanded:
            self._shell_vm.close_right_panel()
        self._device_vm.deselect_device()

    # =========================================================================
    # UI Setup
    # =========================================================================

    def _apply_initial_layout(self) -> None:
        self.ui.right_slide_menu_frame.setFixedWidth(Layout.RIGHT_PANEL_COLLAPSED_WIDTH)
        self.ui.left_slide_menu_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)

        if hasattr(self.ui, "dashboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.dashboard_page)
        elif hasattr(self.ui, "daboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.daboard_page)

    def _init_shell(self) -> None:
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
        )

        self.sidebar = SidebarView(
            container=self.ui.left_slide_menu_frame,
            nav_list=self.ui.listWidget,
            settings_list=self.ui.listWidget_settings,
            shell_vm=self._shell_vm,
        )

        self.right_panel = RightPanelView(
            container=self.ui.right_slide_menu_frame,
            store=self._store,
            device_vm=self._device_vm,
            shell_vm=self._shell_vm,
        )

        self.status_bar = StatusBarView(self.ui.statusbar)

    def _init_workspace(self) -> None:
        logger.info("[MainWindow] Initializing workspace...")

        try:
            dash_config = self._shell_vm.get_layout_config("daboard_midle_frame_1")
            orders_config = self._shell_vm.get_layout_config("orders_midle_frame_1")

            self.canvas_dashboard = self._embed(
                self.ui.daboard_midle_frame_1,
                DeviceCanvasWidget("dashboard", dash_config, self),
            )
            self.device_gantt_dashboard = self._embed(
                self.ui.daboard_midle_frame_2,
                DeviceGanttDisplayWidget(self),
            )
            self.legend_dashboard = self._embed(
                self.ui.daboard_bottom_frame,
                LegendWidget(self),
            )

            self.canvas_orders = self._embed(
                self.ui.orders_midle_frame_1,
                DeviceCanvasWidget("orders", orders_config, self),
            )
            self.device_gantt_orders = self._embed(
                self.ui.orders_midle_frame_2,
                DeviceGanttDisplayWidget(self),
            )
            self.legend_orders = self._embed(
                self.ui.orders_bottom_frame,
                LegendWidget(self),
            )

            # Connect device click signals
            self.canvas_dashboard.device_clicked.connect(self._on_device_single_clicked)
            self.canvas_orders.device_clicked.connect(self._on_device_single_clicked)

            self.canvas_dashboard.device_double_clicked.connect(self._on_device_double_clicked)
            self.canvas_orders.device_double_clicked.connect(self._on_device_double_clicked)

            self.ui.daboard_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)
            self.ui.orders_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)

            self._components_ready = True

            devices = self._device_vm.devices
            if devices:
                is_dark = self._theme_manager.is_dark
                devices_dict = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in devices.items()}
                self.canvas_dashboard.render_state(devices_dict, is_dark)
                self.canvas_orders.render_state(devices_dict, is_dark)

            self.device_gantt_dashboard.show_placeholder()
            self.device_gantt_orders.show_placeholder()

            logger.info("[MainWindow] Workspace initialized")

        except Exception as e:
            logger.error(f"[MainWindow] Workspace init failed: {e}", exc_info=True)

    def _embed(self, parent: QWidget, widget: QWidget) -> QWidget:
        layout = parent.layout()
        if not layout:
            layout = QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        layout.addWidget(widget)
        return widget

    def _apply_theme(self, theme: str) -> None:
        self._theme_manager.set_theme(theme)
        stylesheet = self._theme_manager.get_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)
            self.style().unpolish(self)
            self.style().polish(self)

        self._apply_page_theme(theme)

        if self._components_ready:
            is_dark = theme == "dark"
            self.device_gantt_dashboard.set_theme(is_dark)
            self.device_gantt_orders.set_theme(is_dark)

    def _apply_page_theme(self, theme: str) -> None:
        is_dark = theme == "dark"

        if is_dark:
            page_bg = "#0F172A"
            frame_bg = "rgba(30, 41, 59, 0.6)"
            border = "rgba(51, 65, 85, 0.4)"
        else:
            page_bg = "#F1F5F9"
            frame_bg = "rgba(255, 255, 255, 0.8)"
            border = "rgba(226, 232, 240, 0.6)"

        for page_name in ["daboard_page", "orders_page"]:
            page = getattr(self.ui, page_name, None)
            if page:
                page.setStyleSheet(f"background-color: {page_bg};")

        for frame_name in ["daboard_top_frame", "orders_top_frame"]:
            frame = getattr(self.ui, frame_name, None)
            if frame:
                frame.setStyleSheet(
                    f"""
                    QFrame {{
                        background-color: {frame_bg};
                        border: none;
                        border-bottom: 1px solid {border};
                    }}
                """
                )

        for frame_name in ["daboard_bottom_frame", "orders_bottom_frame"]:
            frame = getattr(self.ui, frame_name, None)
            if frame:
                frame.setStyleSheet(
                    f"""
                    QFrame {{
                        background-color: {frame_bg};
                        border: none;
                        border-top: 1px solid {border};
                    }}
                """
                )

    def _switch_page(self, page: str) -> None:
        page_name = page.replace("dashboard", "daboard") if "dashboard" in page else page
        target = getattr(self.ui, page_name, None)
        if target and self.ui.stackedWidget.currentWidget() != target:
            self.ui.stackedWidget.setCurrentWidget(target)

    def _update_lcd_displays(self, state: Dict[str, Any]) -> None:
        summary = select_factory_summary(state)
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("total_output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        """Handle store state changes (for shell components)."""
        self.sidebar.render(state)
        self.header.render(state)
        self.right_panel.render(state)
        self.status_bar.render(state)
        self._update_lcd_displays(state)
        self._prev_state = state.copy()

    # =========================================================================
    # Window Events
    # =========================================================================

    def closeEvent(self, event) -> None:
        """Handle window close - cleanup event filter."""
        try:
            app = QApplication.instance()
            if app:
                app.removeEventFilter(self)
        except Exception as e:
            logger.debug(f"[MainWindow] Error removing event filter: {e}")

        super().closeEvent(event)


__all__ = ["MainWindow"]
