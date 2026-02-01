"""
Main Window - Optimized for Remote-First Architecture.
Default page: Dashboard
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import QEvent, QRect, QTimer, Slot
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
    select_gantt_data,
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
    from ..controllers.gantt_controller import GanttController
    from ..controllers.shell_controller import ShellController
    from ..services.page_device_manager import PageDeviceManager
    from ..state.store import Store

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: "Store",
        shell_controller: "ShellController",
        page_manager: Optional["PageDeviceManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._store = store
        self._controller = shell_controller
        self._page_manager = page_manager
        self._theme_manager = get_theme_manager()
        self._gantt_controller: Optional["GanttController"] = None

        self._prev_state: Dict[str, Any] = {}
        self._components_ready = False
        self._selected_device_id: Optional[str] = None
        self._current_gantt_segments: List[Dict[str, Any]] = []

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory Production Monitor")

        self._apply_initial_layout()
        self._init_shell()

        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._init_workspace)

        self._setup_shortcuts()
        self._apply_theme("light")

        self._store.state_changed.connect(self._on_state_changed)
        self._store.devices_updated.connect(self._on_devices_updated)

        QApplication.instance().installEventFilter(self)

        logger.info("[MainWindow] Initialized")

    def set_gantt_controller(self, controller: "GanttController") -> None:
        self._gantt_controller = controller
        controller.device_gantt_ready.connect(self._on_gantt_data_ready)
        controller.loading_started.connect(self._on_gantt_loading_started)
        controller.loading_finished.connect(self._on_gantt_loading_finished)
        controller.fetch_error.connect(self._on_gantt_fetch_error)
        logger.info("[MainWindow] Gantt controller connected")

    @Slot(dict)
    def _on_devices_updated(self, devices: Dict[str, Any]) -> None:
        """Handle device updates - render immediately."""
        if not self._components_ready:
            return

        logger.info(f"[MainWindow] Devices updated: {len(devices)} devices")

        is_dark = self._theme_manager.is_dark
        self.canvas_dashboard.render_state(devices, is_dark)
        self.canvas_orders.render_state(devices, is_dark)

    @Slot(str, list)
    def _on_gantt_data_ready(
        self,
        device_code: str,
        segments: List[Dict[str, Any]],
    ) -> None:
        """Handle gantt data ready - update gantt widget and legend."""
        if not self._components_ready:
            return

        if device_code != self._selected_device_id:
            return

        logger.info(f"[MainWindow] Gantt data ready: {device_code}, {len(segments)} segments")

        self._current_gantt_segments = segments

        state = self._store.get_state()
        devices = select_devices(state)
        device_info = devices.get(device_code, {})

        if isinstance(device_info, dict):
            device_name = device_info.get("display_name") or device_info.get("equip_name") or device_code
        else:
            device_name = getattr(device_info, "display_name", None) or getattr(device_info, "equip_name", None) or device_code

        now = datetime.now()
        start = now - timedelta(hours=24)

        # Update gantt widgets
        self.device_gantt_dashboard.render_device_gantt(
            device_code=device_code,
            device_name=device_name,
            segments=segments,
            start_time=start,
            end_time=now,
        )
        self.device_gantt_orders.render_device_gantt(
            device_code=device_code,
            device_name=device_name,
            segments=segments,
            start_time=start,
            end_time=now,
        )

        # Update legend
        self._update_legend_with_segments(device_code, segments, start, now)

    def _update_legend_with_segments(
        self,
        device_code: str,
        segments: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        gantt_data = {device_code: segments}
        self.legend_dashboard.render_stats(gantt_data, start_time, end_time)
        self.legend_orders.render_stats(gantt_data, start_time, end_time)

    @Slot(str)
    def _on_gantt_loading_started(self, device_code: str) -> None:
        pass

    @Slot(str)
    def _on_gantt_loading_finished(self, device_code: str) -> None:
        pass

    @Slot(str, str)
    def _on_gantt_fetch_error(self, device_code: str, error: str) -> None:
        logger.error(f"[MainWindow] Gantt fetch error for {device_code}: {error}")

    def _apply_initial_layout(self) -> None:
        """Set initial layout - Dashboard as default page."""
        self.ui.right_slide_menu_frame.setFixedWidth(Layout.RIGHT_PANEL_COLLAPSED_WIDTH)
        self.ui.left_slide_menu_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)

        # Default to dashboard page
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
            controller=self._controller,
        )

        self.sidebar = SidebarView(
            container=self.ui.left_slide_menu_frame,
            nav_list=self.ui.listWidget,
            settings_list=self.ui.listWidget_settings,
            controller=self._controller,
        )

        self.right_panel = RightPanelView(
            container=self.ui.right_slide_menu_frame,
            store=self._store,
            controller=self._controller,
        )

        self.status_bar = StatusBarView(self.ui.statusbar)

    def _init_workspace(self) -> None:
        logger.info("[MainWindow] Initializing workspace...")

        try:
            dash_config = self._controller.get_layout_config("daboard_midle_frame_1")
            orders_config = self._controller.get_layout_config("orders_midle_frame_1")

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

            # Connect signals: single click -> gantt, double click -> right panel
            self.canvas_dashboard.device_clicked.connect(self._on_device_single_clicked)
            self.canvas_orders.device_clicked.connect(self._on_device_single_clicked)

            self.canvas_dashboard.device_double_clicked.connect(self._on_device_double_clicked)
            self.canvas_orders.device_double_clicked.connect(self._on_device_double_clicked)

            self.ui.daboard_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)
            self.ui.orders_bottom_frame.setMaximumHeight(Layout.LEGEND_HEIGHT)

            self._components_ready = True

            state = self._store.get_state()
            self._on_state_changed(state)

            self.device_gantt_dashboard.show_placeholder()
            self.device_gantt_orders.show_placeholder()

            logger.info("[MainWindow] Workspace initialized")

        except Exception as e:
            logger.error(
                f"[MainWindow] Workspace initialization failed: {e}",
                exc_info=True,
            )

    def _embed(self, parent: QWidget, widget: QWidget) -> QWidget:
        layout = parent.layout()
        if not layout:
            layout = QVBoxLayout(parent)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        layout.addWidget(widget)
        return widget

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._controller.toggle_theme)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._controller.toggle_sidebar_menu)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._controller.toggle_details_panel)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape_pressed)

    def _on_escape_pressed(self) -> None:
        state = self._store.get_state()

        if select_right_panel_expanded(state):
            self._controller.toggle_details_panel()

        self._controller.deselect_device()
        self._selected_device_id = None
        self._current_gantt_segments = []

        if self._components_ready:
            self.device_gantt_dashboard.show_placeholder()
            self.device_gantt_orders.show_placeholder()
            self.legend_dashboard.clear_stats()
            self.legend_orders.clear_stats()

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

    def _on_device_single_clicked(self, device_id: str) -> None:
        """Handle single click - show gantt and legend, don't open panel."""
        logger.info(f"[MainWindow] Device single clicked: {device_id}")

        if device_id == self._selected_device_id:
            # Already selected - check cache
            if self._gantt_controller:
                cached = self._gantt_controller.get_cached_segments(device_id)
                if cached:
                    self._on_gantt_data_ready(device_id, cached)
                    return

        self._selected_device_id = device_id

        if self._components_ready:
            self._show_loading_gantt(device_id, self._store.get_state())

        # Select device without opening panel
        self._controller.select_device_without_panel(device_id)

    def _on_device_double_clicked(self, device_id: str) -> None:
        """Handle double click - show right panel."""
        logger.info(f"[MainWindow] Device double clicked: {device_id}")

        state = self._store.get_state()
        is_panel_open = select_right_panel_expanded(state)

        if device_id != self._selected_device_id:
            self._selected_device_id = device_id
            self._controller.select_device_without_panel(device_id)

            if self._components_ready:
                self._show_loading_gantt(device_id, self._store.get_state())

        # Open panel if not already open
        if not is_panel_open:
            self._controller.toggle_details_panel()

    def _show_loading_gantt(self, device_id: str, state: Dict[str, Any]) -> None:
        devices = select_devices(state)
        device_info = devices.get(device_id, {})

        if isinstance(device_info, dict):
            device_name = device_info.get("display_name") or device_info.get("equip_name") or device_id
        else:
            device_name = getattr(device_info, "display_name", None) or getattr(device_info, "equip_name", None) or device_id

        now = datetime.now()
        start = now - timedelta(hours=24)

        self.device_gantt_dashboard.render_device_gantt(
            device_code=device_id,
            device_name=f"{device_name} (Loading...)",
            segments=[],
            start_time=start,
            end_time=now,
        )
        self.device_gantt_orders.render_device_gantt(
            device_code=device_id,
            device_name=f"{device_name} (Loading...)",
            segments=[],
            start_time=start,
            end_time=now,
        )

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        theme = select_theme(state)
        if theme != self._prev_state.get("theme"):
            self._apply_theme(theme)

        self.sidebar.render(state)
        self.header.render(state)
        self.right_panel.render(state)
        self.status_bar.render(state)

        page = select_current_page(state)
        if page != self._prev_state.get("current_page"):
            self._switch_page(page)

        if not self._components_ready:
            self._prev_state = state.copy()
            return

        devices = select_devices(state)
        devices_changed = devices != self._prev_state.get("devices")
        theme_changed = theme != self._prev_state.get("theme")

        if devices_changed or theme_changed:
            is_dark = self._theme_manager.is_dark
            self.canvas_dashboard.render_state(devices, is_dark)
            self.canvas_orders.render_state(devices, is_dark)

        selected_device_id = select_selected_device_id(state)
        prev_selected = self._prev_state.get("selected_device_id")

        if selected_device_id != prev_selected:
            if not selected_device_id and prev_selected:
                self._selected_device_id = None
                self._current_gantt_segments = []
                self.device_gantt_dashboard.show_placeholder()
                self.device_gantt_orders.show_placeholder()
                self.legend_dashboard.clear_stats()
                self.legend_orders.clear_stats()

        self._update_lcd_displays(state)
        self._prev_state = state.copy()

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

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.MouseButtonPress:
            self._handle_click_outside(event.globalPosition().toPoint())
        return super().eventFilter(obj, event)

    def _handle_click_outside(self, pos) -> None:
        """Handle clicks outside panels."""
        state = self._store.get_state()

        # Handle sidebar
        if select_sidebar_expanded(state):
            if not self._is_inside(pos, self.ui.left_slide_menu_frame):
                if not self._is_inside(pos, self.ui.title_frame):
                    self._controller.toggle_sidebar_menu()

        # Handle right panel
        if select_right_panel_expanded(state):
            if self._is_inside(pos, self.ui.right_slide_menu_frame):
                return

            widget = QApplication.widgetAt(pos)

            if widget:
                widget_class = type(widget).__name__
                if "QGraphicsView" in widget_class:
                    return

                parent = widget
                while parent:
                    if isinstance(parent, DeviceCanvasWidget):
                        break
                    parent = parent.parent() if hasattr(parent, "parent") else None

            self._controller.toggle_details_panel()
            self._controller.deselect_device()
            self._selected_device_id = None

    def _is_inside(self, pos, widget) -> bool:
        if not widget or not widget.isVisible():
            return False
        rect = QRect(widget.mapToGlobal(widget.rect().topLeft()), widget.size())
        return rect.contains(pos)


__all__ = ["MainWindow"]
