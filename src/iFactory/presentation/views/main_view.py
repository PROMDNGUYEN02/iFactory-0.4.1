"""
Main View - Tối thượng UI/UX (Max Level).
FIX: Khắc phục lỗi Header bị trắng. Tích hợp hiển thị dữ liệu phân tích thực tế (OEE, Yield).
"""

from __future__ import annotations
import sys
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QListWidgetItem, QProgressBar, QHBoxLayout, QFrame
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap, QColor
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
        self._setup_right_panel_advanced()  # Nâng cấp UI ở đây
        self._setup_device_canvas()
        self._setup_gantt_chart()
        self._setup_legend()
        self._setup_shortcuts()

        # =====================================================================
        # FIX TỐI THƯỢNG: ÉP UI KHỞI ĐỘNG CHUẨN XÁC
        # =====================================================================
        self.ui.left_slide_menu_frame.setFixedWidth(50)
        self.ui.title_frame.setFixedWidth(50)
        self.ui.title_label.setVisible(False)
        self.ui.title_icon.setVisible(False)

        self._apply_theme(self._current_theme)

        current_state = self._store.get_state()
        if current_state.get("left_menu_expanded", True):
            self._controller.handle_left_menu_toggle()
        # =====================================================================

        self._connect_ui_events()
        self._store.state_changed.connect(self._on_state_changed)

        logger.debug("[MainView] Full Advanced UI Restored.")

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
            self.ui.title_label.setText("iFactory Advanced")
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

    def _setup_right_panel_advanced(self) -> None:
        """Nâng cấp Right Panel thành Dashboard Phân tích Thu nhỏ"""
        if hasattr(self.ui, "right_slide_menu_frame"):
            layout = self.ui.right_slide_menu_frame.layout()
            if not layout:
                layout = QVBoxLayout(self.ui.right_slide_menu_frame)

            layout.setContentsMargins(15, 20, 15, 20)
            layout.setSpacing(12)

            # Tiêu đề & Status Badge
            header_layout = QHBoxLayout()
            self.rp_title = QLabel("SELECT DEVICE")
            self.rp_title.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.rp_status_badge = QLabel("N/A")
            self.rp_status_badge.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(self.rp_title)
            header_layout.addStretch()
            header_layout.addWidget(self.rp_status_badge)
            layout.addLayout(header_layout)

            # Phân tích OEE
            self.lbl_oee = QLabel("OEE (Hiệu suất): 0%")
            self.lbl_oee.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self.bar_oee = QProgressBar()
            self.bar_oee.setTextVisible(False)
            self.bar_oee.setFixedHeight(12)
            layout.addWidget(self.lbl_oee)
            layout.addWidget(self.bar_oee)

            # Phân tích Yield
            self.lbl_yield = QLabel("Yield Rate (Tỷ lệ đạt): 0%")
            self.lbl_yield.setStyleSheet("font-weight: bold; margin-top: 5px;")
            self.bar_yield = QProgressBar()
            self.bar_yield.setTextVisible(False)
            self.bar_yield.setFixedHeight(12)
            layout.addWidget(self.lbl_yield)
            layout.addWidget(self.bar_yield)

            # Thông tin chi tiết (Frame gom nhóm)
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

            # Lỗi gần nhất
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

        self.ui.right_slide_menu_frame.setFixedWidth(320 if self._is_right_panel_open else 0)

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

        # Right Panel - Render Dữ Liệu Thực
        selected_data = select_selected_device_data(state)
        if selected_data and hasattr(self, "rp_title"):
            dev_id = selected_data.get("id", "Unknown")
            status = selected_data.get("status", "Offline")
            color = selected_data.get("color", "#888888")

            # Real metrics từ Redux Store
            inputs = selected_data.get("inputs", 0)
            outputs = selected_data.get("outputs", 0)
            error = selected_data.get("error", "No recent errors")
            oee = selected_data.get("oee", 0)
            yield_rate = selected_data.get("yield_rate", 0)
            cycle_time = selected_data.get("cycle_time", 0.0)

            # Update Header
            self.rp_title.setText(f"MÁY: {dev_id}")
            self.rp_status_badge.setText(status.upper())
            self.rp_status_badge.setStyleSheet(
                f"""
                background-color: {color}; color: white; font-weight: bold; 
                padding: 4px 10px; border-radius: 12px; font-size: 11px;
            """
            )

            # Update Progress Bars
            self.lbl_oee.setText(f"OEE (Hiệu suất): {oee}%")
            self.bar_oee.setValue(int(oee))
            bar_color = "#2ecc71" if oee > 85 else ("#f1c40f" if oee > 60 else "#e74c3c")
            self.bar_oee.setStyleSheet(f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 4px; }}")

            self.lbl_yield.setText(f"Yield Rate: {yield_rate}%")
            self.bar_yield.setValue(int(yield_rate))
            self.bar_yield.setStyleSheet("QProgressBar::chunk { background-color: #3498db; border-radius: 4px; }")

            # Update Details
            self.rp_inputs.setText(f"📥 Đầu vào: <b>{inputs:,}</b> sp")
            self.rp_outputs.setText(f"📦 Đầu ra: <b>{outputs:,}</b> sp")
            self.rp_cycletime.setText(f"⏱️ Cycle Time: <b>{cycle_time}s</b>")

            # Cảnh báo
            self.rp_error.setText(f"⚠️ Cảnh báo: {error}")
            self.rp_error.setStyleSheet(
                "color: #e74c3c; font-weight: bold;" if error != "None" and error != "No recent errors" else "color: #7f8c8d;"
            )

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
