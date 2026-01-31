"""
Main View - Application Shell & Orchestrator.
Refactored to Composition-over-Inheritance pattern.
Optimized with "Invisible Startup" strategy to prevent wrong page flash.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
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
    """

    def __init__(self, store: "Store", controller: "MainController", parent=None):
        super().__init__(parent)
        self._store = store
        self._controller = controller

        # 1. Base Setup
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory Production Monitor")

        # --- CHIẾN LƯỢC KHỞI ĐỘNG "TÀNG HÌNH" ---
        # Ẩn StackedWidget ngay lập tức để tránh hiện trang sai (Orders Page)
        # trong lúc ứng dụng đang load nặng.
        self.ui.stackedWidget.setVisible(False)

        # 2. Force Default Geometry & Page
        self._pre_render_defaults()

        # 3. Initialize Components
        self._init_components()

        # 4. Setup Workspaces
        self._setup_workspaces()

        # 5. Final Wiring
        self._setup_shortcuts()
        self._apply_initial_theme()

        # 6. Subscribe to State & Force Initial Render
        self._store.state_changed.connect(self._on_state_changed)
        QApplication.instance().installEventFilter(self)

        # Hydrate UI with initial state (Sets Sidebar, Theme, etc.)
        initial_state = self._store.get_state()
        self._on_state_changed(initial_state)

        # --- SHOW CONTENT NOW ---
        # Sau khi logic đã chạy xong và page đã được set đúng là Dashboard,
        # chúng ta mới cho hiện widget lên.
        self.ui.stackedWidget.setVisible(True)

        logger.info("[MainView] Shell initialized.")

    def _pre_render_defaults(self):
        """
        Set initial layout state before components load.
        """
        # Force Right Panel Closed
        self.ui.right_slide_menu_frame.setFixedWidth(0)

        # Ensure Left Menu starts at a sane width
        self.ui.left_slide_menu_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)

        # --- CRITICAL FIX: Direct Page Setting ---
        # Chúng ta set cứng trang Dashboard làm trang hiện tại ngay lập tức.
        # Vì stackedWidget đang bị ẩn (setVisible(False)), người dùng sẽ không thấy việc chuyển đổi này.
        if hasattr(self.ui, "daboard_page"):
            self.ui.stackedWidget.setCurrentWidget(self.ui.daboard_page)

    def _init_components(self):
        """Instantiate shell components with defensive binding."""
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

    def _setup_workspaces(self):
        """Initialize the central widgets."""
        self.canvas_dashboard = self._embed_widget(self.ui.daboard_midle_frame_1, DeviceCanvasWidget("daboard_midle_frame_1", self))
        self.canvas_orders = self._embed_widget(self.ui.orders_midle_frame_1, DeviceCanvasWidget("orders_midle_frame_1", self))

        self.canvas_dashboard.device_clicked.connect(self._controller.handle_device_selection)
        self.canvas_orders.device_clicked.connect(self._controller.handle_device_selection)

        self.gantt_dashboard = self._embed_widget(self.ui.daboard_midle_frame_2, GanttCanvasWidget(self))
        self.gantt_orders = self._embed_widget(self.ui.orders_midle_frame_2, GanttCanvasWidget(self))

        self.ui.daboard_bottom_frame.setMaximumHeight(60)
        self.ui.orders_bottom_frame.setMaximumHeight(60)
        self.legend_dashboard = self._embed_widget(self.ui.daboard_bottom_frame, LegendWidget(self))
        self.legend_orders = self._embed_widget(self.ui.orders_bottom_frame, LegendWidget(self))

    def _embed_widget(self, parent_frame: QWidget, widget: QWidget) -> QWidget:
        if not parent_frame.layout():
            QVBoxLayout(parent_frame)
        layout = parent_frame.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return widget

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self._controller.handle_theme_toggle(self._current_theme_mode))
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._controller.handle_left_menu_toggle)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._controller.handle_right_panel_toggle)

    def _apply_initial_theme(self):
        self._current_theme_mode = "light"
        theme_manager.set_theme("light")
        self.setAutoFillBackground(True)
        self._apply_stylesheet("light")

    def _apply_stylesheet(self, mode: str):
        self._current_theme_mode = mode
        theme_manager.set_theme(mode)
        ss = theme_manager.get_stylesheet()
        if ss:
            self.setStyleSheet(ss)
            self.style().unpolish(self)
            self.style().polish(self)

    def _on_state_changed(self, state: Dict[str, Any]):
        """Master State Reactor."""
        # 1. Theme
        theme = select_theme(state)
        if theme != self._current_theme_mode:
            self._apply_stylesheet(theme)

        # 2. Shell Components
        self.sidebar.render(state)
        self.sidebar.set_data_range(select_data_range_days(state))
        self.header.render(state)
        self.right_panel.render(state)
        self.status_bar.render(state)

        # 3. Page Navigation (Robust)
        current_page = select_current_page(state)  # e.g. "daboard_page"

        # Dùng getattr để lấy widget thực tế thay vì findChild
        target_widget = getattr(self.ui, current_page, None)

        if target_widget and self.ui.stackedWidget.currentWidget() != target_widget:
            self.ui.stackedWidget.setCurrentWidget(target_widget)

        # 4. Workspace Content
        devices = select_all_devices(state)
        is_dark = theme_manager.is_dark
        self.canvas_dashboard.render_state(devices, is_dark)
        self.canvas_orders.render_state(devices, is_dark)

        gantt_data = select_gantt_timeline(state)
        now = datetime.now()
        start_24h = now - timedelta(hours=24)

        self.gantt_dashboard.render_timeline(gantt_data, start_24h, now)
        self.gantt_orders.render_timeline(gantt_data, start_24h, now)

        self.legend_dashboard.render_stats(gantt_data, start_24h, now)
        self.legend_orders.render_stats(gantt_data, start_24h, now)

        # 5. LCD Stats
        summary = select_factory_summary(state)
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.MouseButtonPress:
            pos = event.globalPosition().toPoint()

            if select_left_menu_expanded(self._store.get_state()):
                if not self._is_pos_in_widget(pos, self.ui.left_slide_menu_frame) and not self._is_pos_in_widget(pos, self.ui.title_frame):
                    self._controller.handle_left_menu_toggle()

            if select_right_panel_expanded(self._store.get_state()):
                widget_under = QApplication.widgetAt(pos)
                is_canvas = widget_under and "QGraphicsView" in str(type(widget_under))

                if not self._is_pos_in_widget(pos, self.ui.right_slide_menu_frame) and not is_canvas:
                    self._controller.handle_right_panel_toggle()

        return super().eventFilter(obj, event)

    def _is_pos_in_widget(self, pos, widget) -> bool:
        return QRect(widget.mapToGlobal(widget.rect().topLeft()), widget.size()).contains(pos)
