"""
Main View - Primary application window.
Reactive UI driven by Redux Store state changes.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut, QAction, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QVBoxLayout,
    QWidget,
    QMenu,
)

import iFactory.presentation.resources.resources_rc as resources_rc

sys.modules["resources_rc"] = resources_rc

from .ui.generated.main_ui import Ui_MainWindow
from .widgets.gantt_canvas import GanttCanvasWidget
from .widgets.device_canvas import DeviceCanvasWidget
from .widgets.legend_widget import LegendWidget
from ..constants.ui_constants import UIConstants
from ..ui_state.store import Action
from ..ui_state.actions import UIActionType, set_data_range
from ..ui_state.selectors import (
    select_theme,
    select_current_page,
    select_all_devices,
    select_factory_summary,
    select_gantt_timeline,
    select_selected_device_data,
    select_left_menu_expanded,
    select_right_panel_expanded,
    select_selected_device_id,
    select_data_range_days,
)

from ..resources.themes.theme_manager import theme_manager

if TYPE_CHECKING:
    from ..controllers.main_controller import MainController
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class MainView(QMainWindow):
    """
    Main application window with reactive state binding.
    All UI updates are driven by Redux Store state changes.
    """

    def __init__(
        self,
        store: "Store",
        controller: "MainController",
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._controller = controller

        # Initialize Theme EARLY
        self._current_theme = "light"
        theme_manager.set_theme(self._current_theme)

        self._is_menu_open = False
        self._is_right_panel_open = False
        self._selected_menu_index: Optional[int] = 0
        self._last_main_page_index: int = 0

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        dashboard_widget = self.ui.stackedWidget.findChild(QWidget, "daboard_page")
        if dashboard_widget:
            self.ui.stackedWidget.setCurrentWidget(dashboard_widget)
        else:
            self.ui.stackedWidget.setCurrentIndex(0)

        if self.ui.listWidget.count() > 0:
            self.ui.listWidget.setCurrentRow(0)
            self._selected_menu_index = 0
            self._last_main_page_index = 0

        # --- FIX: Prevent Startup Flash ---
        self.setAutoFillBackground(True)
        self._apply_theme(self._current_theme)

        self._setup_initial_state()
        self._setup_header()
        self._setup_left_menu()
        self._setup_right_panel()
        self._setup_device_canvas()
        self._setup_gantt_chart()
        self._setup_legend()
        # self._setup_settings_page()  <-- REMOVED: Using Popup Menu instead
        self._setup_shortcuts()
        self._connect_ui_events()

        # Collapse menu initially
        current_state = self._store.get_state()
        if current_state.get("left_menu_expanded", True):
            self._controller.handle_left_menu_toggle()

        self._store.state_changed.connect(self._on_state_changed)
        QApplication.instance().installEventFilter(self)
        self.update_system_status(mssql_connected=False, sqlite_connected=True, message="Initializing system components...")

        logger.debug("[MainView] Initialized.")

    def _setup_initial_state(self) -> None:
        """Configure initial UI state."""
        self.ui.statusbar.show()
        self.statusBar().setSizeGripEnabled(False)
        self.ui.right_slide_menu_frame.setFixedWidth(0)
        self.ui.left_slide_menu_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_label.setVisible(False)
        self.ui.title_icon.setVisible(False)

        self._setup_status_bar()

    def _setup_status_bar(self) -> None:
        """Modern Status Bar Setup."""
        self.ui.statusbar.setStyleSheet(
            """
            QStatusBar {
                background-color: #FAFAFA;
                border-top: 1px solid #E5E5E5;
                color: #333;
            }
        """
        )

        self.lbl_system_message = QLabel("Ready")
        self.lbl_system_message.setStyleSheet("color: #666666; padding-left: 10px; font-size: 12px;")
        self.ui.statusbar.addWidget(self.lbl_system_message, 1)

        self.status_container = QWidget()
        container_layout = QHBoxLayout(self.status_container)
        container_layout.setContentsMargins(0, 0, 15, 0)
        container_layout.setSpacing(15)

        def create_indicator(text):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                """
                QLabel {
                    background-color: transparent;
                    color: #999999;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 4px 8px;
                    border: 1px solid #E0E0E0;
                    border-radius: 10px;
                }
            """
            )
            return lbl

        self.lbl_sqlite_status = create_indicator("Local DB")
        self.lbl_mssql_status = create_indicator("Remote DB")

        self.lbl_app_mode = QLabel("ONLINE")
        self.lbl_app_mode.setStyleSheet("font-weight: bold; font-size: 11px; color: #10B981;")

        container_layout.addWidget(self.lbl_sqlite_status)
        container_layout.addWidget(self.lbl_mssql_status)

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #CCCCCC;")
        container_layout.addWidget(separator)

        container_layout.addWidget(self.lbl_app_mode)

        self.ui.statusbar.addPermanentWidget(self.status_container)

    def eventFilter(self, obj, event) -> bool:
        """Handle click-outside to close panels."""
        if event.type() == QEvent.MouseButtonPress:
            click_pos = event.globalPosition().toPoint()

            left_menu_rect = QRect(
                self.ui.left_slide_menu_frame.mapToGlobal(self.ui.left_slide_menu_frame.rect().topLeft()),
                self.ui.left_slide_menu_frame.size(),
            )
            header_rect = QRect(
                self.ui.title_frame.mapToGlobal(self.ui.title_frame.rect().topLeft()),
                self.ui.title_frame.size(),
            )

            if self._is_menu_open and not left_menu_rect.contains(click_pos) and not header_rect.contains(click_pos):
                self._controller.handle_left_menu_toggle()

            right_panel_rect = QRect(
                self.ui.right_slide_menu_frame.mapToGlobal(self.ui.right_slide_menu_frame.rect().topLeft()),
                self.ui.right_slide_menu_frame.size(),
            )

            widget_at_click = QApplication.widgetAt(click_pos)
            is_click_on_canvas = widget_at_click and "QGraphicsView" in str(type(widget_at_click))

            if self._is_right_panel_open and not right_panel_rect.contains(click_pos) and not is_click_on_canvas:
                self._controller.handle_right_panel_toggle()

        return super().eventFilter(obj, event)

    def _setup_header(self) -> None:
        if hasattr(self.ui, "title_icon"):
            self.ui.title_icon.setPixmap(QPixmap(":/icon/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.ui.title_icon.setText("")
            self.ui.title_icon.setContentsMargins(10, 0, 0, 0)

        if hasattr(self.ui, "title_label"):
            self.ui.title_label.setText("iFactory")
            self.ui.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        if hasattr(self.ui, "pushButton"):
            self.ui.pushButton.setText("")
            self.ui.pushButton.setIconSize(QSize(20, 20))
            self.ui.pushButton.setCursor(Qt.PointingHandCursor)
            self.ui.pushButton.setToolTip("Toggle Menu (Ctrl+M)")
            self.ui.pushButton.setObjectName("menu_toggle_btn")

        if hasattr(self.ui, "minimize_window_button"):
            self.ui.minimize_window_button.clicked.connect(self.showMinimized)
        if hasattr(self.ui, "restore_window_button"):
            self.ui.restore_window_button.clicked.connect(lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        if hasattr(self.ui, "close_window_button"):
            self.ui.close_window_button.clicked.connect(self.close)

    def _setup_left_menu(self) -> None:
        self.ui.listWidget.clear()
        self.ui.listWidget_settings.clear()

        self.ui.listWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.listWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.listWidget_settings.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ui.listWidget_settings.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        icon_size = QSize(24, 24)
        self.ui.listWidget.setIconSize(icon_size)
        self.ui.listWidget_settings.setIconSize(icon_size)

        pages = [
            ("Dashboard", ":/icon/dashboard.svg", "daboard_page"),
            ("Orders", ":/icon/orders.svg", "orders_page"),
        ]
        for text, icon, page_id in pages:
            item = QListWidgetItem(QIcon(icon), text)
            item.setData(Qt.UserRole, page_id)
            item.setToolTip(text)
            self.ui.listWidget.addItem(item)

        settings_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
        settings_item.setData(Qt.UserRole, "settings_page")
        settings_item.setToolTip("Settings")
        self.ui.listWidget_settings.addItem(settings_item)

    def _setup_right_panel(self) -> None:
        layout = self.ui.right_slide_menu_frame.layout()
        if not layout:
            layout = QVBoxLayout(self.ui.right_slide_menu_frame)

        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        self.rp_title = QLabel("SELECT DEVICE")
        self.rp_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.rp_status_badge = QLabel("N/A")
        self.rp_status_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.rp_title)
        header_layout.addStretch()
        header_layout.addWidget(self.rp_status_badge)
        layout.addLayout(header_layout)

        # Added Description Label
        self.rp_desc = QLabel("")
        self.rp_desc.setStyleSheet("font-size: 12px; font-style: italic; color: #555;")
        self.rp_desc.setWordWrap(True)
        layout.addWidget(self.rp_desc)

        self.rp_last_update = QLabel("Last Update: --")
        self.rp_last_update.setStyleSheet("font-size: 11px; margin-bottom: 5px; color: #808080;")
        layout.addWidget(self.rp_last_update)

        # Material Info Section
        self.rp_material_frame = QFrame()
        self.rp_material_frame.setStyleSheet("background-color: #f5f5f5; border-radius: 6px; padding: 6px;")
        mat_layout = QVBoxLayout(self.rp_material_frame)
        mat_layout.setContentsMargins(5, 5, 5, 5)

        self.rp_material_batch = QLabel("Batch: --")
        self.rp_material_batch.setStyleSheet("font-weight: bold; color: #34495e;")
        self.rp_feeding_time = QLabel("Fed: --")
        self.rp_feeding_time.setStyleSheet("font-size: 10px; color: #7f8c8d;")

        mat_layout.addWidget(self.rp_material_batch)
        mat_layout.addWidget(self.rp_feeding_time)
        layout.addWidget(self.rp_material_frame)

        self.lbl_oee = QLabel("OEE: 0%")
        self.lbl_oee.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.bar_oee = QProgressBar()
        self.bar_oee.setTextVisible(False)
        self.bar_oee.setFixedHeight(12)
        layout.addWidget(self.lbl_oee)
        layout.addWidget(self.bar_oee)

        self.lbl_yield = QLabel("Yield Rate: 0%")
        self.lbl_yield.setStyleSheet("font-weight: bold; margin-top: 5px;")
        self.bar_yield = QProgressBar()
        self.bar_yield.setTextVisible(False)
        self.bar_yield.setFixedHeight(12)
        layout.addWidget(self.lbl_yield)
        layout.addWidget(self.bar_yield)

        self.frame_details = QFrame()
        self.frame_details.setObjectName("frame_details")
        details_layout = QVBoxLayout(self.frame_details)
        details_layout.setContentsMargins(10, 10, 10, 10)

        self.rp_inputs = QLabel("Inputs: 0")
        self.rp_outputs = QLabel("Outputs: 0")
        self.rp_cycletime = QLabel("Cycle Time: 0.0s")

        details_layout.addWidget(self.rp_inputs)
        details_layout.addWidget(self.rp_outputs)
        details_layout.addWidget(self.rp_cycletime)
        layout.addWidget(self.frame_details)

        # --- NEW GANTT CHART IN RIGHT PANEL (COMPACT) ---
        self.lbl_rp_gantt = QLabel("Timeline (Last 24h)")
        self.lbl_rp_gantt.setStyleSheet("font-weight: bold; margin-top: 10px; color: #555;")
        layout.addWidget(self.lbl_rp_gantt)

        # Use Compact Mode
        self.rp_gantt = GanttCanvasWidget(self, is_compact=True)
        self.rp_gantt.setFixedHeight(60)  # Compact fixed height
        layout.addWidget(self.rp_gantt)
        # --------------------------------------

        self.rp_error = QLabel("Last Error: None")
        self.rp_error.setWordWrap(True)
        layout.addWidget(self.rp_error)

        layout.addStretch()

    def _setup_device_canvas(self) -> None:
        if hasattr(self.ui, "daboard_midle_frame_1"):
            self.canvas_dashboard = DeviceCanvasWidget("daboard_midle_frame_1", self)
            self.canvas_dashboard.device_clicked.connect(self._on_device_clicked)
            layout = self.ui.daboard_midle_frame_1.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.daboard_midle_frame_1)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.canvas_dashboard)

        if hasattr(self.ui, "orders_midle_frame_1"):
            self.canvas_orders = DeviceCanvasWidget("orders_midle_frame_1", self)
            self.canvas_orders.device_clicked.connect(self._on_device_clicked)
            layout = self.ui.orders_midle_frame_1.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.orders_midle_frame_1)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.canvas_orders)

    def _setup_gantt_chart(self) -> None:
        if hasattr(self.ui, "daboard_midle_frame_2"):
            self.gantt_dashboard = GanttCanvasWidget(self)
            layout = self.ui.daboard_midle_frame_2.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.daboard_midle_frame_2)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.gantt_dashboard)

        if hasattr(self.ui, "orders_midle_frame_2"):
            self.gantt_orders = GanttCanvasWidget(self)
            layout = self.ui.orders_midle_frame_2.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.orders_midle_frame_2)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.gantt_orders)

    def _setup_legend(self) -> None:
        if hasattr(self.ui, "daboard_bottom_frame"):
            self.ui.daboard_bottom_frame.setMaximumHeight(60)
            self.legend_dashboard = LegendWidget(self)
            layout = self.ui.daboard_bottom_frame.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.daboard_bottom_frame)
            layout.addWidget(self.legend_dashboard)

        if hasattr(self.ui, "orders_bottom_frame"):
            self.ui.orders_bottom_frame.setMaximumHeight(60)
            self.legend_orders = LegendWidget(self)
            layout = self.ui.orders_bottom_frame.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.orders_bottom_frame)
            layout.addWidget(self.legend_orders)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self._controller.handle_theme_toggle(self._current_theme))
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._controller.handle_left_menu_toggle)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._controller.handle_right_panel_toggle)

    def _connect_ui_events(self) -> None:
        self.ui.pushButton.clicked.connect(self._controller.handle_left_menu_toggle)
        self.ui.listWidget.itemClicked.connect(self._on_menu_item_clicked)
        self.ui.listWidget_settings.itemClicked.connect(self._on_settings_clicked)

    def _on_menu_item_clicked(self, item: QListWidgetItem) -> None:
        page_id = item.data(Qt.UserRole)
        row = self.ui.listWidget.row(item)
        self.ui.listWidget_settings.clearSelection()
        self._selected_menu_index = row
        # Track main page for persistence
        self._last_main_page_index = row
        self._controller.handle_navigation(page_id)

    def _on_settings_clicked(self, item: QListWidgetItem) -> None:
        """
        Thay vì chuyển trang, hiển thị Popup Menu để chọn Data Range ngay lập tức.
        """
        # 1. Lấy giá trị hiện tại từ Store để đánh dấu (Check)
        current_days = select_data_range_days(self._store.get_state())

        # 2. Tạo Menu
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px;
                font-size: 13px;
                color: #000000;
            }
            QMenu::item:selected {
                background-color: #E0E0E0;
                color: #000000;
            }
        """
        )

        # 3. Định nghĩa các tùy chọn
        options = [("Last 1 Day", 1), ("Last 1 Week", 7), ("Last 1 Month", 30), ("Last 3 Months", 90)]

        # 4. Tạo Action cho từng tùy chọn
        for text, days in options:
            action = QAction(text, self)
            action.setCheckable(True)

            # Đánh dấu nếu đang được chọn
            if days == current_days:
                action.setChecked(True)

            # Sử dụng lambda để bắt biến 'days'
            action.triggered.connect(lambda chk, d=days: self._store.dispatch(set_data_range(d)))

            menu.addAction(action)

        # 5. Hiển thị Menu tại vị trí con trỏ chuột
        menu.exec(QCursor.pos())

        # 6. Bỏ chọn item trong list widget để không bị "dính" màu selection
        self.ui.listWidget_settings.clearSelection()

        # (Optional) Giữ focus ở trang chính, không chuyển sang trang Settings rỗng
        if self._last_main_page_index is not None:
            self.ui.listWidget.setCurrentRow(self._last_main_page_index)

    def select_menu_item(self, index: int) -> None:
        if 0 <= index < self.ui.listWidget.count():
            self.ui.listWidget.setCurrentRow(index)
            self.ui.listWidget_settings.clearSelection()
            self._selected_menu_index = index
            item = self.ui.listWidget.item(index)
            if item:
                page_id = item.data(Qt.UserRole)
                self._controller.handle_navigation(page_id)

    def _on_device_clicked(self, device_id: str) -> None:
        """Xử lý khi click vào thiết bị: Chọn và tự động mở Right Panel."""
        # 1. Dispatch action chọn thiết bị
        self._controller.handle_device_selection(device_id)

        # 2. KIỂM TRA VÀ MỞ PANEL (VẤN ĐỀ 1)
        current_state = self._store.get_state()
        is_panel_expanded = current_state.get("right_panel_expanded", False)

        if not is_panel_expanded:
            self._controller.handle_right_panel_toggle()

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        theme = select_theme(state)
        page = select_current_page(state)
        devices = select_all_devices(state)
        summary = select_factory_summary(state)
        gantt_data = select_gantt_timeline(state)
        menu_expanded = select_left_menu_expanded(state)
        panel_expanded = select_right_panel_expanded(state)

        self._is_menu_open = menu_expanded
        self._is_right_panel_open = panel_expanded

        if theme != self._current_theme or menu_expanded != self._is_menu_open:
            self._is_menu_open = menu_expanded
            self._apply_theme(theme)

        # UPDATE TOGGLE BUTTON OBJECT NAME FOR STYLING
        if hasattr(self.ui, "pushButton"):
            self.ui.pushButton.setObjectName("menu_close_btn" if menu_expanded else "menu_open_btn")
            self.ui.pushButton.style().unpolish(self.ui.pushButton)
            self.ui.pushButton.style().polish(self.ui.pushButton)

        # Update local state
        self._is_right_panel_open = panel_expanded

        # Page Navigation Logic
        target = self.ui.stackedWidget.findChild(QWidget, page)
        if target and self.ui.stackedWidget.currentWidget() != target:
            self.ui.stackedWidget.setCurrentWidget(target)

        # Persistence Logic: If settings is active, keep main menu highlighted
        if page == "settings_page":
            if self._last_main_page_index is not None:
                self.ui.listWidget.setCurrentRow(self._last_main_page_index)
        else:
            # Sync stored index if state changed externally
            for i in range(self.ui.listWidget.count()):
                item = self.ui.listWidget.item(i)
                if item.data(Qt.UserRole) == page:
                    self.ui.listWidget.setCurrentRow(i)
                    self._last_main_page_index = i
                    self.ui.listWidget_settings.clearSelection()
                    break

        menu_w = UIConstants.MENU_EXPANDED_WIDTH if menu_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self.ui.left_slide_menu_frame.setFixedWidth(menu_w)
        self.ui.title_frame.setFixedWidth(menu_w)
        self.ui.title_label.setVisible(menu_expanded)
        self.ui.title_icon.setVisible(menu_expanded)

        panel_w = UIConstants.RIGHT_PANEL_WIDTH_EXPANDED if panel_expanded else 0
        self.ui.right_slide_menu_frame.setFixedWidth(panel_w)

        is_dark = theme_manager.is_dark
        if hasattr(self, "canvas_dashboard"):
            self.canvas_dashboard.render_state(devices, is_dark)
        if hasattr(self, "canvas_orders"):
            self.canvas_orders.render_state(devices, is_dark)

        # Central Gantt & Legend (System Wide)
        now = datetime.now()
        start_24h = now - timedelta(hours=24)

        if gantt_data:
            if hasattr(self, "gantt_dashboard"):
                self.gantt_dashboard.render_timeline(gantt_data, start_24h, now)
            if hasattr(self, "gantt_orders"):
                self.gantt_orders.render_timeline(gantt_data, start_24h, now)

            # Update Legend for BOTH pages
            if hasattr(self, "legend_dashboard"):
                self.legend_dashboard.render_stats(gantt_data, start_24h, now)
            if hasattr(self, "legend_orders"):
                self.legend_orders.render_stats(gantt_data, start_24h, now)

        self._update_right_panel(state)
        self._update_lcd_numbers(summary)

        sys_status = state.get("system_status", {})
        if hasattr(self, "update_system_status"):
            self.update_system_status(
                mssql_connected=sys_status.get("mssql", False),
                sqlite_connected=sys_status.get("sqlite", False),
                message=state.get("last_log_message", "System Running"),
            )

    def _update_right_panel(self, state: Dict[str, Any]) -> None:
        selected_data = select_selected_device_data(state)
        if not selected_data or not hasattr(self, "rp_title"):
            return

        # Basic Info
        dev_id = selected_data.get("id", "Unknown")
        display_name = selected_data.get("display_name", dev_id)
        desc = selected_data.get("description", "")
        status = selected_data.get("status_display", "Offline")
        color = selected_data.get("status_color", "#888888")

        # Material & Metrics
        batch = selected_data.get("material_batch", "--")
        fed_time = selected_data.get("feeding_time", "--")
        inputs = selected_data.get("input_count", 0)
        outputs = selected_data.get("outputs", 0)
        error = selected_data.get("error", "No recent errors")
        oee = selected_data.get("oee", 0)
        yield_rate = selected_data.get("yield_rate", 0)
        cycle_time = selected_data.get("cycle_time", 0.0)
        last_update = selected_data.get("last_update")

        self.rp_title.setText(display_name)

        if desc:
            self.rp_desc.setText(desc)
            self.rp_desc.setVisible(True)
        else:
            self.rp_desc.setVisible(False)

        if last_update:
            clean_time = str(last_update).replace("T", " ").split(".")[0]
            self.rp_last_update.setText(f"🕒 Last Status: <b>{clean_time}</b>")
        else:
            self.rp_last_update.setText("🕒 Last Status: --")

        self.rp_status_badge.setText(status.upper())
        self.rp_status_badge.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; " f"padding: 4px 10px; border-radius: 12px; font-size: 11px;"
        )

        self.rp_material_batch.setText(f"Batch: {batch}")
        self.rp_feeding_time.setText(f"Fed: {fed_time}")

        self.lbl_oee.setText(f"OEE: {oee}%")
        self.bar_oee.setValue(int(oee))
        bar_color = "#2ecc71" if oee > 85 else ("#f1c40f" if oee > 60 else "#e74c3c")
        self.bar_oee.setStyleSheet(f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}")

        self.lbl_yield.setText(f"Yield Rate: {yield_rate}%")
        self.bar_yield.setValue(int(yield_rate))
        self.bar_yield.setStyleSheet("QProgressBar::chunk { background-color: #3498db; border-radius: 4px; }")

        self.rp_inputs.setText(f"📥 Inputs: <b>{inputs:,}</b>")
        self.rp_outputs.setText(f"📦 Outputs: <b>{outputs:,}</b>")
        self.rp_cycletime.setText(f"⏱️ Cycle Time: <b>{cycle_time}s</b>")

        # --- Update Right Panel Gantt (Specific Device) ---
        gantt_data = select_gantt_timeline(state)
        dev_id_raw = selected_data.get("id")
        if gantt_data and dev_id_raw in gantt_data:
            now = datetime.now()
            start = now - timedelta(hours=24)
            self.rp_gantt.render_timeline({dev_id_raw: gantt_data[dev_id_raw]}, start, now)
        elif hasattr(self, "rp_gantt"):
            self.rp_gantt.render_timeline({})
        # --------------------------------------------------

        self.rp_error.setText(f"⚠️ Alert: {error}")
        has_error = error not in ("None", "No recent errors", None, "")
        self.rp_error.setStyleSheet("color: #e74c3c; font-weight: bold;" if has_error else "color: #7f8c8d;")

    def _update_lcd_numbers(self, summary: Dict[str, Any]) -> None:
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def update_system_status(self, mssql_connected: bool = False, sqlite_connected: bool = False, message: str = None) -> None:
        COLOR_SUCCESS_BG = "#D1FAE5"
        COLOR_SUCCESS_TEXT = "#065F46"
        COLOR_SUCCESS_BORDER = "#10B981"
        COLOR_ERROR_BG = "#FEE2E2"
        COLOR_ERROR_TEXT = "#991B1B"
        COLOR_ERROR_BORDER = "#EF4444"
        COLOR_WARN_BG = "#FEF3C7"
        COLOR_WARN_TEXT = "#92400E"
        COLOR_WARN_BORDER = "#F59E0B"

        def set_style(label, state, text_ok, text_err):
            if state:
                label.setText(f"● {text_ok}")
                label.setStyleSheet(
                    f"""
                    background-color: {COLOR_SUCCESS_BG}; 
                    color: {COLOR_SUCCESS_TEXT}; 
                    border: 1px solid {COLOR_SUCCESS_BG}; 
                    border-radius: 12px; padding: 2px 10px; font-weight: bold;
                """
                )
            else:
                label.setText(f"○ {text_err}")
                label.setStyleSheet(
                    f"""
                    background-color: {COLOR_ERROR_BG}; 
                    color: {COLOR_ERROR_TEXT}; 
                    border: 1px solid {COLOR_ERROR_BG};
                    border-radius: 12px; padding: 2px 10px; font-weight: bold;
                """
                )

        set_style(self.lbl_mssql_status, mssql_connected, "Remote: On", "Remote: Off")
        set_style(self.lbl_sqlite_status, sqlite_connected, "Local: On", "Local: Err")

        if mssql_connected and sqlite_connected:
            self.lbl_app_mode.setText("ONLINE SYSTEM")
            self.lbl_app_mode.setStyleSheet(f"color: {COLOR_SUCCESS_BORDER}; font-weight: 900;")
        elif not mssql_connected and sqlite_connected:
            self.lbl_app_mode.setText("OFFLINE MODE")
            self.lbl_app_mode.setStyleSheet(f"color: {COLOR_WARN_BORDER}; font-weight: 900;")
        else:
            self.lbl_app_mode.setText("SYSTEM HALTED")
            self.lbl_app_mode.setStyleSheet(f"color: {COLOR_ERROR_BORDER}; font-weight: 900;")

        if message:
            time_str = datetime.now().strftime("%H:%M:%S")
            self.lbl_system_message.setText(f"[{time_str}] {message}")

    def _update_menu_icons(self, mode: str) -> None:
        btn_key = ":/icon/close.svg" if self._is_menu_open else ":/icon/open.svg"
        self.ui.pushButton.setIcon(QIcon(theme_manager.get_icon_path(btn_key)))

        for i in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(i)
            page_id = item.data(Qt.UserRole)
            icon_key = ":/icon/dashboard.svg" if "daboard" in page_id else ":/icon/orders.svg"
            item.setIcon(QIcon(theme_manager.get_icon_path(icon_key)))

        settings_item = self.ui.listWidget_settings.item(0)
        if settings_item:
            settings_item.setIcon(QIcon(theme_manager.get_icon_path(":/icon/settings.svg")))

    def _apply_theme(self, mode: str) -> None:
        self._current_theme = mode
        theme_manager.set_theme(mode)
        self._update_menu_icons(mode)
        stylesheet = theme_manager.get_stylesheet()
        if stylesheet:
            self.setStyleSheet(stylesheet)
            # --- FIX: Force Polish ---
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        else:
            logger.warning("Empty stylesheet generated.")


__all__ = ["MainView"]
