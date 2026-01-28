"""
Main View - Primary application window.
Reactive UI driven by Redux Store state changes.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Dict, Any, Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
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
)

# [CRITICAL FIX] Use 'as' to capture the module directly.
# This avoids accessing 'iFactory.presentation' while it is still initializing.
import iFactory.presentation.resources.resources_rc as resources_rc

# Map the aliased module to sys.modules so generated UI files can find "resources_rc"
sys.modules["resources_rc"] = resources_rc

from .ui.generated.main_ui import Ui_MainWindow
from .widgets.gantt_canvas import GanttCanvasWidget
from .widgets.device_canvas import DeviceCanvasWidget
from .widgets.legend_widget import LegendWidget
from ..constants.ui_constants import UIConstants
from ..ui_state.store import Action
from ..ui_state.actions import UIActionType
from ..ui_state.selectors import (
    select_theme,
    select_current_page,
    select_all_devices,
    select_factory_summary,
    select_gantt_timeline,
    select_selected_device_data,
    select_left_menu_expanded,
    select_right_panel_expanded,
)

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
        self._current_theme = "light"
        self._is_menu_open = False
        self._is_right_panel_open = False
        self._selected_menu_index: Optional[int] = None

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._setup_initial_state()
        self._setup_header()
        self._setup_left_menu()
        self._setup_right_panel()
        self._setup_device_canvas()
        self._setup_gantt_chart()
        self._setup_legend()
        self._setup_shortcuts()
        self._connect_ui_events()

        self._apply_theme(self._current_theme)

        # Collapse menu initially
        current_state = self._store.get_state()
        if current_state.get("left_menu_expanded", True):
            self._controller.handle_left_menu_toggle()

        self._store.state_changed.connect(self._on_state_changed)
        QApplication.instance().installEventFilter(self)

        logger.debug("[MainView] Initialized.")

    def _setup_initial_state(self) -> None:
        """Configure initial UI state."""
        self.ui.statusbar.hide()
        self.statusBar().setSizeGripEnabled(False)
        self.ui.right_slide_menu_frame.setFixedWidth(0)
        self.ui.left_slide_menu_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_frame.setFixedWidth(UIConstants.MENU_COLLAPSED_WIDTH)
        self.ui.title_label.setVisible(False)
        self.ui.title_icon.setVisible(False)

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
        """Configure header bar."""
        if hasattr(self.ui, "title_icon"):
            self.ui.title_icon.setPixmap(QPixmap(":/icon/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.ui.title_icon.setText("")
            self.ui.title_icon.setContentsMargins(10, 0, 0, 0)

        if hasattr(self.ui, "title_label"):
            self.ui.title_label.setText("iFactory")
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
        """Configure left navigation menu."""
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
            self.ui.listWidget.addItem(item)

        settings_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
        settings_item.setData(Qt.UserRole, "settings_page")
        self.ui.listWidget_settings.addItem(settings_item)

        # Select first item (Dashboard) by default
        if self.ui.listWidget.count() > 0:
            self.ui.listWidget.setCurrentRow(0)
            self._selected_menu_index = 0

    def _setup_right_panel(self) -> None:
        """Configure right detail panel."""
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

        self.rp_error = QLabel("Last Error: None")
        self.rp_error.setWordWrap(True)
        layout.addWidget(self.rp_error)

        layout.addStretch()

    def _setup_device_canvas(self) -> None:
        """Configure device visualization canvases."""
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
        """Configure Gantt chart widgets."""
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
        """Configure legend widgets."""
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
        """Configure keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self._controller.handle_theme_toggle(self._current_theme))
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._controller.handle_left_menu_toggle)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._controller.handle_right_panel_toggle)

    def _connect_ui_events(self) -> None:
        """Connect UI widget signals to controller."""
        self.ui.pushButton.clicked.connect(self._controller.handle_left_menu_toggle)
        self.ui.listWidget.itemClicked.connect(self._on_menu_item_clicked)
        self.ui.listWidget_settings.itemClicked.connect(self._on_settings_clicked)

    def _on_menu_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle menu item click with selection update."""
        page_id = item.data(Qt.UserRole)
        row = self.ui.listWidget.row(item)

        # Clear settings selection
        self.ui.listWidget_settings.clearSelection()

        # Update selection state
        self._selected_menu_index = row

        # Navigate to page
        self._controller.handle_navigation(page_id)

    def _on_settings_clicked(self, item: QListWidgetItem) -> None:
        """Handle settings menu click."""
        page_id = item.data(Qt.UserRole)

        # Clear main menu selection
        self.ui.listWidget.clearSelection()

        # Update selection state
        self._selected_menu_index = -1  # Settings is special

        # Navigate to page
        self._controller.handle_navigation(page_id)

    def select_menu_item(self, index: int) -> None:
        """Public method to select menu item by index."""
        if 0 <= index < self.ui.listWidget.count():
            self.ui.listWidget.setCurrentRow(index)
            self.ui.listWidget_settings.clearSelection()
            self._selected_menu_index = index

            # Also navigate to the page
            item = self.ui.listWidget.item(index)
            if item:
                page_id = item.data(Qt.UserRole)
                self._controller.handle_navigation(page_id)

    def _on_device_clicked(self, device_id: str) -> None:
        """Handle device selection from canvas."""
        self._store.dispatch(Action(type=UIActionType.DEVICE_SELECTED.value, payload={"id": device_id}))
        if not self._is_right_panel_open:
            self._controller.handle_right_panel_toggle()

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        """React to Redux store state changes."""
        theme = select_theme(state)
        page = select_current_page(state)
        devices = select_all_devices(state)
        summary = select_factory_summary(state)
        gantt_data = select_gantt_timeline(state)
        menu_expanded = select_left_menu_expanded(state)
        panel_expanded = select_right_panel_expanded(state)

        if theme != self._current_theme or menu_expanded != self._is_menu_open:
            self._is_menu_open = menu_expanded
            self._apply_theme(theme)

        self._is_right_panel_open = panel_expanded

        # Navigate to page
        target = self.ui.stackedWidget.findChild(QWidget, page)
        if target and self.ui.stackedWidget.currentWidget() != target:
            self.ui.stackedWidget.setCurrentWidget(target)

        # Update menu width
        menu_w = UIConstants.MENU_EXPANDED_WIDTH if menu_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self.ui.left_slide_menu_frame.setFixedWidth(menu_w)
        self.ui.title_frame.setFixedWidth(menu_w)
        self.ui.title_label.setVisible(menu_expanded)
        self.ui.title_icon.setVisible(menu_expanded)

        # Update right panel width
        panel_w = UIConstants.RIGHT_PANEL_WIDTH_EXPANDED if panel_expanded else 0
        self.ui.right_slide_menu_frame.setFixedWidth(panel_w)

        # Update canvases
        is_dark = theme == "dark"
        if hasattr(self, "canvas_dashboard"):
            self.canvas_dashboard.render_state(devices, is_dark)
        if hasattr(self, "canvas_orders"):
            self.canvas_orders.render_state(devices, is_dark)

        # Update Gantt charts
        if hasattr(self, "gantt_dashboard") and gantt_data:
            self.gantt_dashboard.render_timeline(gantt_data)
        if hasattr(self, "gantt_orders") and gantt_data:
            self.gantt_orders.render_timeline(gantt_data)

        self._update_right_panel(state)
        self._update_lcd_numbers(summary)

    def _update_right_panel(self, state: Dict[str, Any]) -> None:
        """Update right panel with selected device data."""
        selected_data = select_selected_device_data(state)
        if not selected_data or not hasattr(self, "rp_title"):
            return

        dev_id = selected_data.get("id", "Unknown")
        status = selected_data.get("status", "Offline")
        color = selected_data.get("color", "#888888")

        inputs = selected_data.get("inputs", 0)
        outputs = selected_data.get("outputs", 0)
        error = selected_data.get("error", "No recent errors")
        oee = selected_data.get("oee", 0)
        yield_rate = selected_data.get("yield_rate", 0)
        cycle_time = selected_data.get("cycle_time", 0.0)

        self.rp_title.setText(f"DEVICE: {dev_id}")
        self.rp_status_badge.setText(status.upper())
        self.rp_status_badge.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold; " f"padding: 4px 10px; border-radius: 12px; font-size: 11px;"
        )

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

        self.rp_error.setText(f"⚠️ Alert: {error}")
        has_error = error not in ("None", "No recent errors", None, "")
        self.rp_error.setStyleSheet("color: #e74c3c; font-weight: bold;" if has_error else "color: #7f8c8d;")

    def _update_lcd_numbers(self, summary: Dict[str, Any]) -> None:
        """Update LCD number displays with factory summary."""
        if hasattr(self.ui, "lcdNumber_20"):
            self.ui.lcdNumber_20.display(summary.get("output", 0))
        if hasattr(self.ui, "lcdNumber_15"):
            self.ui.lcdNumber_15.display(summary.get("yield_rate", 0))

    def _update_menu_icons(self, mode: str) -> None:
        """Update menu icons based on theme."""
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
        """Apply theme stylesheet."""
        self._current_theme = mode
        self._update_menu_icons(mode)

        common_qss = """
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
                icon-size: 24px;
            }
            QListWidget::item {
                padding-left: 10px;
                height: 45px;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton#pushButton {
                background: transparent;
                border: none;
                padding-left: 10px;
                text-align: left;
            }
        """

        if mode == "dark":
            colors = """
                QMainWindow, QWidget {
                    background-color: #1e1e1e;
                    color: #ffffff;
                }
                QLabel { color: #ffffff; }
                QFrame#left_slide_menu_frame,
                QFrame#right_slide_menu_frame,
                QFrame#title_frame {
                    background-color: #252526;
                }
                QListWidget::item { color: #ffffff; }
                QListWidget::item:hover,
                QPushButton#pushButton:hover {
                    background-color: #3e3e42;
                }
                QListWidget::item:selected {
                    background-color: #094771;
                    color: white;
                    border-left: 3px solid #007acc;
                }
            """
        else:
            colors = """
                QMainWindow, QWidget {
                    background-color: #f3f3f3;
                    color: #000000;
                }
                QLabel { color: #000000; }
                QFrame#left_slide_menu_frame,
                QFrame#right_slide_menu_frame,
                QFrame#title_frame {
                    background-color: #ffffff;
                }
                QListWidget::item { color: #000000; }
                QListWidget::item:hover,
                QPushButton#pushButton:hover {
                    background-color: #e8e8e8;
                }
                QListWidget::item:selected {
                    background-color: #e3f2fd;
                    color: #007acc;
                    border-left: 3px solid #007acc;
                }
            """

        self.setStyleSheet(common_qss + colors)


__all__ = ["MainView"]
