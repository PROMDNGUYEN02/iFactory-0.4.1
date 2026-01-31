"""
Main View - Application Shell & Orchestrator.
Refactored to Reactive Composition-over-Inheritance pattern.
Includes State Diffing, Lazy Loading, and Configuration Injection.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional

from PySide6.QtCore import QEvent, QRect, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout

import iFactory.presentation.resources.resources_rc as resources_rc

sys.modules["resources_rc"] = resources_rc

from .ui.generated.main_ui import Ui_MainWindow
from ..constants.ui_constants import UIConstants
from ..resources.themes.theme_manager import theme_manager

# Child Components
from .shell.sidebar import SidebarView
from .shell.header import HeaderView
from .shell.right_panel import RightPanelView
from .shell.status_bar import StatusBarView
from .widgets.device_canvas import DeviceCanvasWidget
from .widgets.gantt_canvas import GanttCanvasWidget
from .widgets.legend_widget import LegendWidget

# State
from ..ui_state.selectors import (
    select_theme,
    select_current_page,
    select_all_devices,
    select_factory_summary,
    select_gantt_timeline,
    select_data_range_days,
    select_left_menu_expanded,
    select_right_panel_expanded,
)

if TYPE_CHECKING:
    from ..controllers.main_controller import MainController
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class MainView(QMainWindow):
    """
    Top-level application window.
    Acts as a Passive View reacting to State changes.
    """

    def __init__(self, store: "Store", controller: "MainController", parent=None):
        super().__init__(parent)
        self._store = store
        self._controller = controller

        # State Memoization for Performance (Diffing)
        self._last_state: Dict[str, Any] = {}
        self._current_theme_mode: Optional[str] = None
        self._components_initialized = False

        # 1. Base UI Setup (Fast)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory Production Monitor")

        # 2. Optimization: Invisible Startup
        self.ui.stackedWidget.setVisible(False)
        self._apply_pre_render_layout_defaults()

        # 3. Component Initialization (Shell Only)
        self._init_shell_components()

        # 4. Schedule Heavy Widget Loading (Deferred)
        QTimer.singleShot(50, self._init_workspace_components_deferred)

        # 5. Input & Theme Configuration
        self._setup_global_shortcuts()
        self._apply_initial_theme()

        # 6. Reactive Wiring
        self._store.state_changed.connect(self._on_state_changed)
        QApplication.instance().installEventFilter(self)

        # 7. Reveal Shell
        self.ui.stackedWidget.setVisible(True)
        logger.info("[MainView] Shell initialized. Workspace loading deferred.")

    def _apply_pre_render_layout_defaults(self):
        """Set initial geometric properties to prevent visual jumping."""
        self.ui.right_slide_menu_frame.setFixedWidth(0)
        self.ui.left_slide_menu_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)

        if hasattr(self.ui, "daboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.daboard_page)

    def _init_shell_components(self):
        """Initialize permanent shell components (Sidebar, Header, etc)."""
        self.header = HeaderView(
            container_frame=self.ui.title_frame,
            toggle_btn=getattr(self.ui, "pushButton", None),
            title_label=getattr(self.ui, "title_label", None),
            title_icon=getattr(self.ui, "title_icon", None),
            min_btn=getattr(self.ui, "minimize_window_button", None),
            restore_btn=getattr(self.ui, "restore_window_button", None),
            close_btn=getattr(self.ui, "close_window_button", None),
            controller=self._controller,
        )

        self.sidebar = SidebarView(
            container_frame=self.ui.left_slide_menu_frame,
            nav_list=self.ui.listWidget,
            settings_list=self.ui.listWidget_settings,
            controller=self._controller,
        )

        self.right_panel = RightPanelView(container_frame=self.ui.right_slide_menu_frame, main_window=self, controller=self._controller)

        self.status_bar = StatusBarView(self.ui.statusbar)

    def _init_workspace_components_deferred(self):
        """
        Initialize dynamic workspace widgets (Canvases, Gantt charts).
        Injects Configuration (Layouts) retrieved from Controller.
        """
        logger.info("[MainView] initializing workspace components...")
        try:
            # Retrieve Layout Config via Controller (Separation of Concerns)
            dash_config = self._controller.get_layout_config("daboard_midle_frame_1")
            orders_config = self._controller.get_layout_config("orders_midle_frame_1")

            # Dashboard Workspace
            self.canvas_dashboard = self._embed_widget(self.ui.daboard_midle_frame_1, DeviceCanvasWidget("daboard_midle_frame_1", dash_config, self))
            self.gantt_dashboard = self._embed_widget(self.ui.daboard_midle_frame_2, GanttCanvasWidget(self))
            self.legend_dashboard = self._embed_widget(self.ui.daboard_bottom_frame, LegendWidget(self))

            # Orders/Analytics Workspace
            self.canvas_orders = self._embed_widget(self.ui.orders_midle_frame_1, DeviceCanvasWidget("orders_midle_frame_1", orders_config, self))
            self.gantt_orders = self._embed_widget(self.ui.orders_midle_frame_2, GanttCanvasWidget(self))
            self.legend_orders = self._embed_widget(self.ui.orders_bottom_frame, LegendWidget(self))

            # Event Wiring
            self.canvas_dashboard.device_clicked.connect(self._controller.handle_device_selection)
            self.canvas_orders.device_clicked.connect(self._controller.handle_device_selection)

            # Layout Constraints
            self.ui.daboard_bottom_frame.setMaximumHeight(60)
            self.ui.orders_bottom_frame.setMaximumHeight(60)

            self._components_initialized = True

            # Force a re-render of the workspace
            current_state = self._store.get_state()
            self._on_state_changed(current_state)

            logger.info("[MainView] Workspace fully initialized.")

        except Exception as e:
            logger.error(f"[MainView] Failed to initialize workspace: {e}", exc_info=True)

    def _embed_widget(self, parent_frame: QWidget, widget: QWidget) -> QWidget:
        """Helper to safely embed a child widget into a UI frame."""
        if not parent_frame.layout():
            layout = QVBoxLayout(parent_frame)
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout = parent_frame.layout()
        layout.addWidget(widget)
        return widget

    def _setup_global_shortcuts(self):
        """Register global application hotkeys."""
        shortcuts = [
            ("Ctrl+T", lambda: self._controller.handle_theme_toggle(self._current_theme_mode)),
            ("Ctrl+M", self._controller.handle_left_menu_toggle),
            ("Ctrl+R", self._controller.handle_right_panel_toggle),
        ]
        for seq, callback in shortcuts:
            QShortcut(QKeySequence(seq), self).activated.connect(callback)

    def _apply_initial_theme(self):
        """Set the default theme state."""
        self._current_theme_mode = "light"
        theme_manager.set_theme("light")
        self.setAutoFillBackground(True)
        self._apply_stylesheet("light")

    def _apply_stylesheet(self, mode: str):
        """Apply the global stylesheet and polish the UI."""
        self._current_theme_mode = mode
        theme_manager.set_theme(mode)
        ss = theme_manager.get_stylesheet()
        if ss:
            self.setStyleSheet(ss)
            self.style().unpolish(self)
            self.style().polish(self)

    def _on_state_changed(self, state: Dict[str, Any]):
        """
        Reactive State Reactor.
        Updates components only when data changes.
        """
        # 1. Theme (Global)
        new_theme = select_theme(state)
        if new_theme != self._current_theme_mode:
            self._apply_stylesheet(new_theme)

        # 2. Navigation & Layout (Shell)
        self.sidebar.render(state)
        self.sidebar.set_data_range(select_data_range_days(state))
        self.header.render(state)
        self.right_panel.render(state)
        self.status_bar.render(state)

        # 3. Page Routing
        current_page_name = select_current_page(state)
        if self._last_state.get("current_page") != current_page_name:
            self._update_active_page(current_page_name)

        # 4. Workspace Content (Lazy Loaded)
        if not self._components_initialized:
            return

        devices = select_all_devices(state)
        devices_changed = devices != self._last_state.get("devices")
        theme_changed = new_theme != self._last_state.get("theme")

        if devices_changed or theme_changed:
            is_dark = theme_manager.is_dark
            if hasattr(self, "canvas_dashboard"):
                self.canvas_dashboard.render_state(devices, is_dark)
            if hasattr(self, "canvas_orders"):
                self.canvas_orders.render_state(devices, is_dark)

        # 5. Gantt & Analytics
        gantt_data = select_gantt_timeline(state)
        gantt_changed = gantt_data != self._last_state.get("gantt_timeline")

        if gantt_changed and hasattr(self, "gantt_dashboard"):
            now = datetime.now()
            start_24h = now - timedelta(hours=24)
            self.gantt_dashboard.render_timeline(gantt_data, start_24h, now)
            self.gantt_orders.render_timeline(gantt_data, start_24h, now)
            self.legend_dashboard.render_stats(gantt_data, start_24h, now)
            self.legend_orders.render_stats(gantt_data, start_24h, now)

        # 6. LCD / Summary Stats
        self._update_summary_stats(state)

        self._last_state = state

    def _update_active_page(self, page_name: str):
        target_widget = getattr(self.ui, page_name, None)
        if target_widget and self.ui.stackedWidget.currentWidget() != target_widget:
            self.ui.stackedWidget.setCurrentWidget(target_widget)

    def _update_summary_stats(self, state: Dict[str, Any]):
        summary = select_factory_summary(state)
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def eventFilter(self, obj, event) -> bool:
        """Global event filter for click-away behavior."""
        if event.type() == QEvent.MouseButtonPress:
            self._handle_global_click(event.globalPosition().toPoint())
        return super().eventFilter(obj, event)

    def _handle_global_click(self, pos):
        state = self._store.get_state()
        if select_left_menu_expanded(state):
            if not (self._is_pos_in_widget(pos, self.ui.left_slide_menu_frame) or self._is_pos_in_widget(pos, self.ui.title_frame)):
                self._controller.handle_left_menu_toggle()

        if select_right_panel_expanded(state):
            widget_under = QApplication.widgetAt(pos)
            is_canvas = widget_under and "QGraphicsView" in str(type(widget_under))
            if not (self._is_pos_in_widget(pos, self.ui.right_slide_menu_frame) or is_canvas):
                self._controller.handle_right_panel_toggle()

    def _is_pos_in_widget(self, pos, widget) -> bool:
        if not widget or not widget.isVisible():
            return False
        return QRect(widget.mapToGlobal(widget.rect().topLeft()), widget.size()).contains(pos)
