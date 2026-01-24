"""
Main Controller - Điều phối trung tâm.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal
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
        self._initialized = False
        logger.info("[MainController] Khởi tạo thành công")

    # --- PHƯƠNG THỨC UICONTAINER YÊU CẦU ---
    def set_view(self, view):
        self._view = view

    def set_device_controller(self, ctrl):
        pass

    def set_navigation_controller(self, ctrl):
        pass

    def set_managers(self, **kwargs):
        pass

    def set_infrastructure_managers(self, device_layout=None, gantt=None, legend=None):
        self._gantt_mgr = gantt
        if self._view and hasattr(self._view, "set_tooltip_provider"):
            self._view.set_tooltip_provider(self._get_device_tooltip_data)

    def update_device_cache(self, statuses=None, **kwargs) -> None:
        if statuses:
            for s in statuses:
                code = s.get("equip_code")
                if code:
                    self._device_status_cache[code] = s

    def _get_device_tooltip_data(self, code: str) -> dict:
        return {"status": self._device_status_cache.get(code, {}), "input": {}, "output": {}}

    def handle_device_click(self, code: str, name: str) -> None:
        """Fix lỗi thiếu hàm xử lý click."""
        if self._async_executor:
            self._async_executor.run(self._load_device_history(code))

    def _inject_managers_into_view(self) -> None:
        if not self._view:
            return

        # 1. FIX: Hiển thị tên Hệ thống trên Left Menu
        if hasattr(self._view, "ui"):
            self._view.ui.title_label.setText("IFACTORY MS - QUẢN LÝ")
            self._view.ui.title_label.show()

        # 2. FIX: Nạp lại Background SVG cho Middle Frame 1
        if self._device_layout_mgr:
            for frame_name in ["daboard_midle_frame_1", "orders_midle_frame_1"]:
                path = self._get_frame_svg_path(frame_name, self._current_mode)
                if path:
                    self._device_layout_mgr.load_svg_for_frame(frame_name, path)

        if hasattr(self._view, "set_tooltip_provider"):
            self._view.set_tooltip_provider(self._get_device_tooltip_data)

    def _show_device_context_menu(self, code: str, name: str, pos: QPoint) -> None:
        """3. FIX: Lỗi không chuột phải được - Tạo QMenu tại vị trí click."""
        if not self._view:
            return
        menu = QMenu(self._view)
        # Style cho menu chuẩn UI hiện đại
        menu.setStyleSheet(
            "QMenu { background-color: #ffffff; border: 1px solid #dcdcdc; padding: 5px; } "
            "QMenu::item:selected { background-color: #0078d7; color: white; }"
        )

        act_history = QAction(f"Xem Gantt: {code}", menu)
        act_history.triggered.connect(lambda: self.handle_device_click(code, name))

        menu.addAction(act_history)
        # Sử dụng QCursor để lấy vị trí global chính xác
        menu.exec(QCursor.pos())

    async def _load_device_history(self, code: str) -> None:
        """Fix lỗi thiếu hàm load history."""
        try:
            if not self._device_service:
                return
            segments = await self._device_service.get_gantt_segments(code)
            converted = [(s.start_time, s.end_time, getattr(s, "status_code", "0")) for s in segments]

            cur_page = self._view.get_current_page() if self._view else "daboard_page"
            frame = "daboard_midle_frame_2" if "daboard" in cur_page else "orders_midle_frame_2"

            if self._gantt_mgr:
                self._gantt_mgr.set_data(frame, code, converted)
        except Exception as e:
            logger.error(f"Load history failed: {e}")

    async def initialize(self):
        self._initialized = True

    def shutdown(self):
        self._initialized = False
