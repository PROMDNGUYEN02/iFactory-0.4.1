"""
Main View - Tối thượng UI/UX.
FIX: Khắc phục lỗi Header bị trắng khi khởi động. Ép vẽ Icon ngay lập tức.
"""

from __future__ import annotations
import sys
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QListWidgetItem
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap
from PySide6.QtCore import Qt, QSize, QEvent, QRect

import iFactory.resources.resources_rc

sys.modules["resources_rc"] = iFactory.resources.resources_rc

from .ui.generated.main_ui import Ui_MainWindow
from .widgets.gantt_canvas import GanttCanvasWidget
from .widgets.device_canvas import DeviceCanvasWidget
from .widgets.legend_widget import LegendWidget

from ..ui_state.store import Action
from ..ui_state.actions import UIActionType
from ..ui_state.selectors import (
    select_theme,
    select_current_page,
    select_all_devices,
    select_factory_summary,
    select_gantt_timeline,
    select_selected_device_data,
)

logger = logging.getLogger(__name__)


class MainView(QMainWindow):
    def __init__(self, store, controller, parent=None):
        super().__init__(parent)
        self._store = store
        self._controller = controller
        self._current_theme = "light"

        self._is_menu_open = False
        self._is_right_panel_open = False

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.statusbar.hide()
        self.statusBar().setSizeGripEnabled(False)
        self.ui.right_slide_menu_frame.setFixedWidth(0)

        QApplication.instance().installEventFilter(self)

        self._setup_header()
        self._setup_left_menu()
        self._setup_right_panel()
        self._setup_device_canvas()
        self._setup_gantt_chart()
        self._setup_legend()
        self._setup_shortcuts()

        # =====================================================================
        # FIX TỐI THƯỢNG: ÉP UI KHỞI ĐỘNG CHUẨN XÁC
        # =====================================================================
        # 1. Ép giao diện thu nhỏ
        self.ui.left_slide_menu_frame.setFixedWidth(50)
        self.ui.title_frame.setFixedWidth(50)
        self.ui.title_label.setVisible(False)
        self.ui.title_icon.setVisible(False)

        # 2. FIX LỖI "TRẮNG HEADER": Ép vẽ Icon Open và áp dụng Theme ngay lập tức
        self._apply_theme(self._current_theme)

        # 3. Đồng bộ với Redux
        current_state = self._store.get_state()
        if current_state.get("left_menu_expanded", True):
            self._controller.handle_left_menu_toggle()
        # =====================================================================

        self._connect_ui_events()
        self._store.state_changed.connect(self._on_state_changed)

        logger.debug("[MainView] Full UI Restored.")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            click_pos = event.globalPosition().toPoint()

            left_menu_rect = QRect(
                self.ui.left_slide_menu_frame.mapToGlobal(self.ui.left_slide_menu_frame.rect().topLeft()), self.ui.left_slide_menu_frame.size()
            )
            header_rect = QRect(self.ui.title_frame.mapToGlobal(self.ui.title_frame.rect().topLeft()), self.ui.title_frame.size())

            if self._is_menu_open and not left_menu_rect.contains(click_pos) and not header_rect.contains(click_pos):
                self._controller.handle_left_menu_toggle()

            right_panel_rect = QRect(
                self.ui.right_slide_menu_frame.mapToGlobal(self.ui.right_slide_menu_frame.rect().topLeft()), self.ui.right_slide_menu_frame.size()
            )

            is_click_on_canvas = False
            widget_at_click = QApplication.widgetAt(click_pos)
            if widget_at_click and "QGraphicsView" in str(type(widget_at_click)):
                is_click_on_canvas = True

            if self._is_right_panel_open and not right_panel_rect.contains(click_pos) and not is_click_on_canvas:
                self._controller.handle_right_panel_toggle()

        return super().eventFilter(obj, event)

    def _setup_header(self) -> None:
        if hasattr(self.ui, "title_icon"):
            self.ui.title_icon.setPixmap(QPixmap(":/icon/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.ui.title_icon.setText("")
            self.ui.title_icon.setContentsMargins(10, 0, 0, 0)

        if hasattr(self.ui, "title_label"):
            self.ui.title_label.setText("Welcome to iFactory")
            self.ui.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        if hasattr(self.ui, "pushButton"):
            self.ui.pushButton.setText("")
            self.ui.pushButton.setIconSize(QSize(24, 24))
            self.ui.pushButton.setCursor(Qt.PointingHandCursor)

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

        pages = [("Dashboard", ":/icon/dashboard.svg", "daboard_page"), ("Orders", ":/icon/orders.svg", "orders_page")]
        for text, icon, page_id in pages:
            item = QListWidgetItem(QIcon(icon), text)
            item.setData(Qt.UserRole, page_id)
            self.ui.listWidget.addItem(item)

        settings_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
        settings_item.setData(Qt.UserRole, "settings_page")
        self.ui.listWidget_settings.addItem(settings_item)

    def _setup_right_panel(self) -> None:
        if hasattr(self.ui, "right_slide_menu_frame"):
            self.rp_title = QLabel("NO DEVICE SELECTED")
            self.rp_title.setAlignment(Qt.AlignCenter)
            self.rp_status = QLabel("Status: N/A")
            self.rp_inputs = QLabel("Inputs: 0")
            self.rp_outputs = QLabel("Outputs: 0")
            self.rp_error = QLabel("Last Error: None")

            layout = self.ui.right_slide_menu_frame.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.right_slide_menu_frame)
                layout.setContentsMargins(0, 0, 0, 0)

            layout.addWidget(self.rp_title)
            layout.addWidget(self.rp_status)
            layout.addWidget(self.rp_inputs)
            layout.addWidget(self.rp_outputs)
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
        self.ui.listWidget.itemClicked.connect(lambda item: self._controller.handle_navigation(item.data(Qt.UserRole)))
        self.ui.listWidget_settings.itemClicked.connect(lambda item: self._controller.handle_navigation(item.data(Qt.UserRole)))

    def _on_device_clicked(self, device_id: str) -> None:
        self._store.dispatch(Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id}))
        if not self._is_right_panel_open:
            self._controller.handle_right_panel_toggle()

    def _on_state_changed(self, state: dict) -> None:
        theme = select_theme(state)
        page = select_current_page(state)
        devices = select_all_devices(state)
        summary = select_factory_summary(state)
        gantt_data = select_gantt_timeline(state)
        menu_expanded = state.get("left_menu_expanded", False)
        self._is_right_panel_open = state.get("right_panel_expanded", False)

        if theme != self._current_theme or menu_expanded != self._is_menu_open:
            self._is_menu_open = menu_expanded
            self._apply_theme(theme)

        # Navigation
        target = self.ui.stackedWidget.findChild(QWidget, page)
        if target and self.ui.stackedWidget.currentWidget() != target:
            self.ui.stackedWidget.setCurrentWidget(target)

        menu_w = 240 if menu_expanded else 50
        self.ui.left_slide_menu_frame.setFixedWidth(menu_w)
        self.ui.title_frame.setFixedWidth(menu_w)

        self.ui.title_label.setVisible(menu_expanded)
        self.ui.title_icon.setVisible(menu_expanded)

        self.ui.right_slide_menu_frame.setFixedWidth(300 if self._is_right_panel_open else 0)

        # Canvas & Gantt
        is_dark = theme == "dark"
        if hasattr(self, "canvas_dashboard"):
            self.canvas_dashboard.render_state(devices, is_dark)
        if hasattr(self, "canvas_orders"):
            self.canvas_orders.render_state(devices, is_dark)
        if hasattr(self, "gantt_dashboard"):
            self.gantt_dashboard.render_timeline(gantt_data)
        if hasattr(self, "gantt_orders"):
            self.gantt_orders.render_timeline(gantt_data)

        # Right Panel
        selected_data = select_selected_device_data(state)
        if selected_data and hasattr(self, "rp_title"):
            dev_id = selected_data.get("id", "Unknown")
            status = selected_data.get("status", "Loading...")
            color = selected_data.get("color", "#888888")
            inputs = selected_data.get("inputs", 0)
            outputs = selected_data.get("outputs", 0)
            error = selected_data.get("error", "None")

            self.rp_title.setText(f"MACHINE: {dev_id}")
            text_color = "#ffffff" if is_dark else "#000000"
            sec_text_color = "#cccccc" if is_dark else "#444444"

            self.rp_title.setStyleSheet(f"font-size: 16px; font-weight: bold; padding: 10px; color: {text_color}; border-bottom: 2px solid #555;")
            self.rp_status.setText(f"Status: {status}")
            self.rp_status.setStyleSheet(f"font-size: 14px; padding: 8px 15px; color: {color}; font-weight: bold;")

            info_qss = f"font-size: 14px; padding: 8px 15px; color: {sec_text_color};"
            self.rp_inputs.setText(f"Inputs: {inputs:,} units")
            self.rp_outputs.setText(f"Outputs: {outputs:,} units")
            self.rp_error.setText(f"Last Error: {error}")
            self.rp_inputs.setStyleSheet(info_qss)
            self.rp_outputs.setStyleSheet(info_qss)
            self.rp_error.setStyleSheet("font-size: 14px; padding: 8px 15px; color: #ff6b6b;")

        self._update_lcd_numbers(summary)

    def _update_lcd_numbers(self, summary: dict) -> None:
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def _update_menu_icons(self, mode: str) -> None:
        suffix = "-white.svg" if mode == "dark" else ".svg"
        btn_icon = "close" if self._is_menu_open else "open"
        self.ui.pushButton.setIcon(QIcon(f":/icon/{btn_icon}{suffix}"))

        for i in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(i)
            page_id = item.data(Qt.UserRole)
            icon_name = "dashboard" if "daboard" in page_id else "orders"
            item.setIcon(QIcon(f":/icon/{icon_name}{suffix}"))

        settings_item = self.ui.listWidget_settings.item(0)
        if settings_item:
            settings_item.setIcon(QIcon(f":/icon/settings{suffix}"))

    def _apply_theme(self, mode: str) -> None:
        self._current_theme = mode
        self._update_menu_icons(mode)

        common_qss = """
            QListWidget { background: transparent; border: none; outline: none; icon-size: 24px; }
            QListWidget::item { padding-left: 10px; height: 45px; font-size: 14px; font-weight: 500; text-align: left; }
            QPushButton#pushButton { background: transparent; border: none; padding-left: 10px; text-align: left; }
        """

        if mode == "dark":
            colors = """
                QMainWindow, QWidget { background-color: #1e1e1e; color: #ffffff; }
                QLabel { color: #ffffff; }
                QFrame#left_slide_menu_frame, QFrame#right_slide_menu_frame, QFrame#title_frame { background-color: #252526; }
                QListWidget::item { color: #ffffff; }
                QListWidget::item:hover, QPushButton#pushButton:hover { background-color: #3e3e42; }
                QListWidget::item:selected { background-color: #094771; color: white; border-left: 3px solid #007acc; }
            """
        else:
            colors = """
                QMainWindow, QWidget { background-color: #f3f3f3; color: #000000; }
                QLabel { color: #000000; }
                QFrame#left_slide_menu_frame, QFrame#right_slide_menu_frame, QFrame#title_frame { background-color: #ffffff; }
                QListWidget::item { color: #000000; }
                QListWidget::item:hover, QPushButton#pushButton:hover { background-color: #e8e8e8; }
                QListWidget::item:selected { background-color: #e3f2fd; color: #007acc; border-left: 3px solid #007acc; }
            """

        self.setStyleSheet(common_qss + colors)


__all__ = ["MainView"]
