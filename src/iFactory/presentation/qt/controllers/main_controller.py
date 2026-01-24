"""
Main Controller - Standardized API and English UI.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal, QPoint, Qt
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction, QCursor

logger = logging.getLogger(__name__)


class MainController(QObject):
    theme_changed = Signal(str)
    device_status_updated = Signal(dict)
    right_panel_data_ready = Signal(dict)

    def __init__(self, device_service=None, async_executor=None, device_presenter=None, gantt_presenter=None, parent=None):
        super().__init__(parent)
        self._device_service = device_service
        self._async_executor = async_executor
        self._device_presenter = device_presenter
        self._gantt_presenter = gantt_presenter

        self._device_status_cache = {}
        self._view = None
        self._gantt_mgr = None
        self._device_layout_mgr = None
        self._current_mode = "light"
        self._initialized = False

    def set_view(self, view):
        self._view = view
        if hasattr(self._view, "ui"):
            # FIX: Ensure English titles in Left Menu
            self._view.ui.title_label.setText("IFACTORY MANAGEMENT SYSTEM")
            self._view.ui.title_label.show()

    def set_device_controller(self, ctrl):
        pass

    def set_navigation_controller(self, ctrl):
        pass

    def set_managers(self, **kwargs):
        pass

    def set_infrastructure_managers(self, device_layout=None, gantt=None, legend=None):
        self._device_layout_mgr = device_layout
        self._gantt_mgr = gantt
        self._inject_managers_into_view()
        self._load_initial_layouts()

    def _load_initial_layouts(self):
        """FIX: Restore missing background layouts."""
        if self._device_layout_mgr:
            for f_name in ["daboard_midle_frame_1", "orders_midle_frame_1"]:
                path = self._get_frame_svg_path(f_name, self._current_mode)
                if path:
                    self._device_layout_mgr.load_svg_for_frame(f_name, path)

    def _show_device_context_menu(self, code: str, name: str, pos: QPoint) -> None:
        """FIX: Full Right-Click Menu (English)."""
        if not self._view:
            return
        menu = QMenu(self._view)
        menu.setStyleSheet("QMenu { background-color: #ffffff; color: #333; border: 1px solid #ccc; }")

        # Header items
        menu.addAction(f"Device: {code}").setEnabled(False)
        menu.addSeparator()

        # Actions
        act_gantt = QAction("📊 Show Gantt Chart", menu)
        act_gantt.triggered.connect(lambda: self.handle_device_click(code, name))

        act_history = QAction("📋 View Status History", menu)
        act_history.triggered.connect(lambda: self._request_right_panel(code, name, "status"))

        menu.addActions([act_gantt, act_history])
        menu.exec(QCursor.pos())

    def _request_right_panel(self, code, name, h_type):
        self.right_panel_data_ready.emit({"type": "history", "device": code, "name": name, "history_type": h_type})

    def handle_device_click(self, device_code: str, device_name: str) -> None:
        if self._async_executor:
            self._async_executor.run(self._load_device_history(device_code))

    async def _load_device_history(self, code: str) -> None:
        """FIX: Proper mapping to avoid 'No Data' in Gantt."""
        if not self._device_service or not self._gantt_mgr:
            return
        try:
            segments = await self._device_service.get_gantt_segments(code)
            # Ensure proper tuple structure (start, end, label)
            converted = [(s.start_time, s.end_time, str(getattr(s, "status_code", "0"))) for s in segments]

            page = self._view.get_current_page() if self._view else "daboard_page"
            frame = "daboard_midle_frame_2" if "daboard" in page else "orders_midle_frame_2"

            self._gantt_mgr.set_data(frame, code, converted)
        except Exception as e:
            logger.error(f"Gantt load failed for {code}: {e}")

    def update_device_cache(self, statuses=None, **kwargs):
        if statuses:
            for s in statuses:
                c = s.get("equip_code") or s.get("EQUIP_CODE")
                if c:
                    self._device_status_cache[c] = s

    def _get_device_tooltip_data(self, code: str) -> dict:
        return {"status": self._device_status_cache.get(code, {}), "input": {}, "output": {}}

    def _get_frame_svg_path(self, f, m):
        d = {
            "daboard_midle_frame_1": {"light": ":/icon/dashboard_layout.svg", "dark": ":/icon/dashboard_layout-white.svg"},
            "orders_midle_frame_1": {"light": ":/icon/orders_layout.svg", "dark": ":/icon/orders_layout-white.svg"},
        }
        return d.get(f, {}).get(m)

    def _inject_managers_into_view(self):
        if self._view and hasattr(self._view, "set_tooltip_provider"):
            self._view.set_tooltip_provider(self._get_device_tooltip_data)
        if self._view and hasattr(self._view, "set_context_menu_provider"):
            self._view.set_context_menu_provider(self._show_device_context_menu)

    async def initialize(self):
        self._initialized = True

    def shutdown(self):
        self._initialized = False
