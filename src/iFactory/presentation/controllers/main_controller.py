"""
Main Controller - Orchestrates UI Intent to Application Actions.
Clean Architecture Compliant: NO direct UI imports, NO direct view mutation.
"""

from __future__ import annotations
import logging
from PySide6.QtCore import QObject
from ..ui_state.actions import change_theme, navigate_page, UIActionType
from ..ui_state.store import Action

logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Handles user intent from the main window.
    Dispatches actions to the Redux store.
    """

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        # Lưu reference đến AppContainer (thường được inject hoặc truy cập qua global nếu cần thiết,
        # nhưng ở đây giả định MainWindow sẽ set cho controller hoặc pass qua constructor)
        # Trong kiến trúc hiện tại, View gọi Controller, Controller gọi Store/Service.
        # Để gọi Application Layer, Controller cần access tới AppContainer hoặc ServiceAdapter.
        self._app_container = None
        logger.debug("[MainController] Initialized.")

    def set_container(self, container):
        """Inject AppContainer to access Application Layer services."""
        self._app_container = container

    def handle_theme_toggle(self, current_mode: str) -> None:
        """User requested theme change."""
        new_mode = "dark" if current_mode == "light" else "light"
        self._store.dispatch(change_theme(new_mode))

    def handle_navigation(self, page_name: str) -> None:
        """User clicked a menu item."""
        self._store.dispatch(navigate_page(page_name))

    def handle_left_menu_toggle(self) -> None:
        """Toggle left menu visibility state."""
        self._store.dispatch(Action(type=UIActionType.LEFT_MENU_TOGGLED.value))

    def handle_right_panel_toggle(self) -> None:
        """Toggle right panel visibility state."""
        self._store.dispatch(Action(type=UIActionType.RIGHT_PANEL_TOGGLED.value))

    async def load_gantt_chart(self, days: int = 1, main_window=None) -> None:
        """
        Tải dữ liệu Gantt và vẽ lên Widget.
        """
        if not self._app_container or not main_window:
            logger.warning("Cannot load Gantt: AppContainer or MainWindow missing.")
            return

        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=days)

        # 1. Lấy danh sách máy từ Store (đã load trước đó)
        devices = self._store.get_state().get("devices", {})
        timeline_data = {}

        logger.info(f"Loading Gantt Chart for {len(devices)} devices...")

        # 2. Query lịch sử từng máy
        for code in devices.keys():
            # Gọi Query qua Adapter/Facade
            result = await self._app_container.device_facade.generate_gantt_segments(code, days=days)
            segments_dto = result["segments"]

            # 3. Convert sang định dạng Widget (dict + percent)
            total_seconds = (end - start).total_seconds()
            formatted_segments = []

            # Map màu sắc cơ bản (Có thể thay bằng logic lấy từ Theme/Config)
            # 1: Run (Green), 2: Stop (Red), 3: Idle/Off (Gray), etc.
            color_map = {"1": "#2ecc71", "2": "#e74c3c", "3": "#95a5a6", "0": "#95a5a6"}  # Run  # Stop  # Off/Idle  # Unknown

            for seg in segments_dto:
                duration = (seg["end_time"] - seg["start_time"]).total_seconds()
                percent = duration / total_seconds if total_seconds > 0 else 0

                status_code = str(seg["status_code"])
                color = color_map.get(status_code, "#7f8c8d")

                formatted_segments.append(
                    {
                        "start_time": seg["start_time"].strftime("%H:%M"),
                        "end_time": seg["end_time"].strftime("%H:%M"),
                        "status_name": seg.get("status_name", status_code),
                        "status_code": status_code,
                        "color": color,
                        "percent": percent,
                    }
                )

            timeline_data[code] = formatted_segments

        # 4. Update UI (Render trực tiếp lên Widget của Main Window)
        if hasattr(main_window, "gantt_widget"):
            main_window.gantt_widget.render_timeline(timeline_data)
        else:
            logger.warning("MainWindow does not have 'gantt_widget'.")


__all__ = ["MainController"]
