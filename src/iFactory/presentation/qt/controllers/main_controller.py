"""
Main Controller - Refactored with Presenter Delegation.

Refactoring:
- Injected DevicePresenter and GanttPresenter.
- Controllers now strictly orchestrate UseCases and Presenters.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QMenu

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget
    from iFactory.application.services.__init__ import DeviceDataService
    from iFactory.presentation.managers import ThemeManager, IconManager
    from iFactory.presentation.qt.presenters import DevicePresenter, GanttPresenter
    from iFactory.config import SettingsManager
    from iFactory.infrastructure.configuration.device_config_loader import (
        DeviceLayoutManager,
    )
    from iFactory.presentation.managers.ui.widgets.gantt.manager import TimelineSegmentFactory, GanttManager
    from iFactory.infrastructure.configuration.legend.manager import LegendManager
logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Main Controller - Complete Integration.

    Responsibilities:
        - Coordinate View with Infrastructure managers
        - Bridge UI events to Application services
        - Provide tooltip/context menu data (via Presenters)
        - Handle theme and settings
        - Manage device visualization lifecycle
    """

    theme_changed = Signal(str)
    device_status_updated = Signal(dict)
    device_selected = Signal(str, str)
    gantt_data_ready = Signal(str, list, object, object)
    right_panel_data_ready = Signal(dict)

    def __init__(
        self,
        device_service: Optional["DeviceDataService"] = None,
        async_executor: Optional[Any] = None,
        device_presenter: Optional["DevicePresenter"] = None,
        gantt_presenter: Optional["GanttPresenter"] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize main controller."""
        super().__init__(parent)
        self._device_service = device_service
        self._async_executor = async_executor
        self._device_presenter = device_presenter
        self._gantt_presenter = gantt_presenter
        self._device_controller = None
        self._navigation_controller = None
        self._device_layout_mgr: Optional["DeviceLayoutManager"] = None
        self._gantt_mgr: Optional["GanttManager"] = None
        self._legend_mgr: Optional["LegendManager"] = None
        self._theme_manager: Optional["ThemeManager"] = None
        self._icon_manager: Optional["IconManager"] = None
        self._settings_manager: Optional["SettingsManager"] = None
        self._view = None
        self._device_status_cache: Dict[str, Dict[str, Any]] = {}
        self._device_input_cache: Dict[str, Dict[str, Any]] = {}
        self._device_output_cache: Dict[str, Dict[str, Any]] = {}
        self._current_mode = "light"
        self._initialized = False
        self._device_update_timer = QTimer(self)
        self._device_update_timer.setSingleShot(True)
        self._device_update_timer.setInterval(50)
        self._device_update_timer.timeout.connect(self._on_device_timer)
        logger.info("[MainController] Created (Refactored)")

    def set_view(self, view: "QWidget") -> None:
        """Set main view reference."""
        self._view = view
        # FIX: Connect controller signals to view methods
        if hasattr(view, "_on_right_panel_data_ready"):
            self.right_panel_data_ready.connect(view._on_right_panel_data_ready)
        logger.debug("[MainController] View set")

    def set_device_controller(self, controller: Any) -> None:
        """Set device controller reference."""
        self._device_controller = controller
        logger.debug("[MainController] Device controller set")

    def set_navigation_controller(self, controller: Any) -> None:
        """Set navigation controller reference."""
        self._navigation_controller = controller
        logger.debug("[MainController] Navigation controller set")

    def set_managers(self, theme: "ThemeManager", icon: "IconManager", settings: "SettingsManager") -> None:
        """Set presentation managers."""
        self._theme_manager = theme
        self._icon_manager = icon
        self._settings_manager = settings
        if settings:
            self._current_mode = settings.theme or "light"
        logger.debug("[MainController] Managers set")

    def set_infrastructure_managers(
        self,
        device_layout: Optional["DeviceLayoutManager"] = None,
        gantt: Optional["GanttManager"] = None,
        legend: Optional["LegendManager"] = None,
    ) -> None:
        """
        Set infrastructure managers and inject into view.
        """
        self._device_layout_mgr = device_layout
        self._gantt_mgr = gantt
        self._legend_mgr = legend
        logger.debug("[MainController] Infrastructure managers set")
        self._inject_managers_into_view()
        if self._device_layout_mgr:
            self._setup_device_layout_callbacks()

    def _inject_managers_into_view(self) -> None:
        """Inject infrastructure managers into view."""
        if not self._view:
            return
        if hasattr(self._view, "set_device_layout_manager"):
            self._view.set_device_layout_manager(self._device_layout_mgr)
            logger.debug("[MainController] DeviceLayoutManager injected into view")
        if hasattr(self._view, "set_gantt_manager"):
            self._view.set_gantt_manager(self._gantt_mgr)
            logger.debug("[MainController] GanttManager injected into view")
        if hasattr(self._view, "set_legend_manager"):
            self._view.set_legend_manager(self._legend_mgr)
            logger.debug("[MainController] LegendManager injected into view")
        self._setup_view_providers()

    def _setup_view_providers(self) -> None:
        """Setup tooltip and context menu providers in view."""
        if not self._view:
            return
        if hasattr(self._view, "set_tooltip_provider"):
            self._view.set_tooltip_provider(self._get_device_tooltip_data)
            logger.debug("[MainController] Tooltip provider set in view")
        if hasattr(self._view, "set_context_menu_provider"):
            self._view.set_context_menu_provider(self._show_device_context_menu)
            logger.debug("[MainController] Context menu provider set in view")

    def _setup_device_layout_callbacks(self) -> None:
        """Setup device layout manager callbacks."""
        if not self._device_layout_mgr:
            return
        self._device_layout_mgr.set_click_callback(lambda code, name: self.handle_device_click(code, name))
        self._device_layout_mgr.set_context_menu_callback(lambda code, name, pos: self._show_device_context_menu(code, name, pos))
        self._device_layout_mgr.set_tooltip_callback(lambda code: self._get_device_tooltip_data(code))
        logger.debug("[MainController] Device layout callbacks setup")

    def _setup_gantt_callbacks(self) -> None:
        """Setup gantt manager callbacks."""
        if not self._gantt_mgr:
            return
        if hasattr(self._gantt_mgr, "segment_clicked"):
            self._gantt_mgr.segment_clicked.connect(lambda frame, segment: self._on_gantt_segment_clicked(frame, segment))
        logger.debug("[MainController] Gantt callbacks setup")

    async def initialize(self) -> None:
        """Initialize controller and load initial data."""
        if self._initialized:
            return
        logger.info("[MainController] Initializing...")
        self._initialize_infrastructure_managers()
        QTimer.singleShot(300, self._load_initial_gantt_data)
        self._initialized = True
        logger.info("[MainController] Initialized")

    def _initialize_infrastructure_managers(self) -> None:
        """Initialize infrastructure managers with view frames."""
        if not self._view:
            logger.warning("[MainController] No view available")
            return
        device_frames = self._get_frames_by_type("device")
        gantt_frames = self._get_frames_by_type("gantt")
        legend_frames = self._get_frames_by_type("legend")
        if self._device_layout_mgr:
            self._init_device_layout_manager(device_frames)
        if self._gantt_mgr:
            self._init_gantt_manager(gantt_frames)
        if self._legend_mgr:
            self._init_legend_manager(legend_frames)
        logger.info("[MainController] Infrastructure managers initialized")

    def _get_frames_by_type(self, frame_type: str) -> Dict[str, Any]:
        """Get frame widgets by type from view."""
        if not self._view or not hasattr(self._view, "ui"):
            return {}
        patterns = {
            "device": ["daboard_midle_frame_1", "orders_midle_frame_1"],
            "gantt": ["daboard_midle_frame_2", "orders_midle_frame_2"],
            "legend": ["daboard_bottom_frame", "orders_bottom_frame"],
        }
        frame_names = patterns.get(frame_type, [])
        return {name: getattr(self._view.ui, name, None) for name in frame_names if hasattr(self._view.ui, name)}

    def _init_device_layout_manager(self, frames: Dict[str, Any]) -> None:
        """Initialize device layout manager with frames."""
        if not self._device_layout_mgr or not frames:
            return
        try:
            self._device_layout_mgr.set_theme(self._current_mode)
            for name, frame in frames.items():
                if frame:
                    self._device_layout_mgr.register_frame(name, frame)
                    svg_path = self._get_frame_svg_path(name, self._current_mode)
                    if svg_path:
                        self._device_layout_mgr.load_svg_for_frame(name, svg_path)
            logger.info(f"[MainController] Device layout initialized: {len(frames)} frames")
        except Exception as e:
            logger.error(f"[MainController] Device layout init failed: {e}")

    def _init_gantt_manager(self, frames: Dict[str, Any]) -> None:
        """Initialize gantt manager with frames."""
        if not self._gantt_mgr or not frames:
            return
        try:
            self._gantt_mgr.set_theme(self._current_mode)
            for name, frame in frames.items():
                if frame:
                    self._gantt_mgr.register_frame(name, frame, show_summary=False, min_height=38)
            logger.info(f"[MainController] Gantt initialized: {len(frames)} frames")
        except Exception as e:
            logger.error(f"[MainController] Gantt init failed: {e}")

    def _init_legend_manager(self, frames: Dict[str, Any]) -> None:
        """Initialize legend manager with frames."""
        if not self._legend_mgr or not frames:
            return
        try:
            self._legend_mgr.set_theme(self._current_mode)
            for name, frame in frames.items():
                if frame:
                    self._legend_mgr.register_frame(name, frame)
            logger.info(f"[MainController] Legend initialized: {len(frames)} frames")
        except Exception as e:
            logger.error(f"[MainController] Legend init failed: {e}")

    def _get_frame_svg_path(self, frame_name: str, mode: str) -> Optional[str]:
        """Get SVG background path for frame."""
        svg_mapping = {
            "daboard_midle_frame_1": {
                "light": ":/icon/dashboard_layout.svg",
                "dark": ":/icon/dashboard_layout-white.svg",
            },
            "orders_midle_frame_1": {
                "light": ":/icon/orders_layout.svg",
                "dark": ":/icon/orders_layout-white.svg",
            },
        }
        frame_svgs = svg_mapping.get(frame_name, {})
        return frame_svgs.get(mode)

    def _load_initial_gantt_data(self) -> None:
        """Load initial gantt data for default devices."""
        if not self._gantt_mgr or not self._device_service:
            return
        default_devices = {
            "daboard_midle_frame_2": "AMX01",
            "orders_midle_frame_2": "CWD01",
        }
        for frame_name, device_code in default_devices.items():
            if self._async_executor:
                self._async_executor.run(self._load_gantt_data(device_code, frame_name))

    def _get_device_tooltip_data(self, device_code: str) -> Dict[str, Any]:
        """Get tooltip data for device."""
        return {
            "status": self._device_status_cache.get(device_code, {}),
            "input": self._device_input_cache.get(device_code, {}),
            "output": self._device_output_cache.get(device_code, {}),
        }

    def update_device_cache(
        self,
        statuses: Optional[List[Dict]] = None,
        inputs: Optional[List[Dict]] = None,
        outputs: Optional[List[Dict]] = None,
    ) -> None:
        """Update device data cache."""
        if statuses:
            for status in statuses:
                code = status.get("EQUIP_CODE") or status.get("equip_code")
                if code:
                    self._device_status_cache[code] = status
        if inputs:
            for inp in inputs:
                code = inp.get("EQUIP_CODE") or inp.get("equip_code")
                if code:
                    self._device_input_cache[code] = inp
        if outputs:
            for out in outputs:
                code = out.get("EQUIP_CODE") or out.get("equip_code")
                if code:
                    self._device_output_cache[code] = out

    def _show_device_context_menu(self, code: str, name: str, pos: "QPoint") -> None:
        """Show rich context menu for device."""
        logger.debug(f"[MainController] Context menu for {code}")
        try:
            menu = self._create_device_context_menu(code, name)
            menu.exec(pos)
        except Exception as e:
            logger.error(f"[MainController] Context menu failed: {e}")

    def _create_device_context_menu(self, code: str, name: str) -> QMenu:
        """Create context menu for device."""
        menu = QMenu(self._view)
        menu.setStyleSheet(
            """
            QMenu {
                background: palette(window);
                border:1px solid palette(mid);
                padding:4px;
                border-radius:4px;
            }
            QMenu::item {
                padding: 8px 24px 8px 16px;
                border-radius:2px;
            }
            QMenu::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QMenu::separator {
                height:1px;
                background: palette(mid);
                margin:4px 8px;
            }
        """
        )
        header = menu.addAction(f"📱 {code}")
        header.setEnabled(False)
        sub_header = menu.addAction(f"   {name}")
        sub_header.setEnabled(False)
        status_data = self._device_status_cache.get(code, {})
        if status_data:
            status_code = status_data.get("EQUIP_STATUS") or status_data.get("status_code", "0")
            status_text = self._format_status_display(status_code)
            status_action = menu.addAction(f"   Status: {status_text}")
            status_action.setEnabled(False)
        menu.addSeparator()
        history_action = menu.addAction("📊  Status History")
        history_action.triggered.connect(lambda: self._on_history_requested(code, name, "status"))
        input_action = menu.addAction("📥  Input History")
        input_action.triggered.connect(lambda: self._on_history_requested(code, name, "input"))
        output_action = menu.addAction("📤  Output History")
        output_action.triggered.connect(lambda: self._on_history_requested(code, name, "output"))
        menu.addSeparator()
        gantt_action = menu.addAction("📈  Show Gantt Chart")
        gantt_action.triggered.connect(lambda: self._on_show_gantt(code))
        return menu

    def _on_history_requested(self, code: str, name: str, history_type: str) -> None:
        """Handle history request from context menu."""
        logger.debug(f"[MainController] History requested: {code} ({history_type})")
        if self._view and hasattr(self._view, "set_right_panel_visible"):
            pass
            self.right_panel_data_ready.emit(
                {
                    "type": "history",
                    "device": code,
                    "history_type": history_type,
                    "name": name,
                }
            )

    def _on_show_gantt(self, code: str) -> None:
        """Handle show gantt from context menu."""
        logger.debug(f"[MainController] Gantt requested: {code}")
        current_page = self._view.get_current_page() if self._view else None
        if current_page:
            gantt_frame = self._get_gantt_frame_for_page(current_page)
            if gantt_frame and self._async_executor:
                self._async_executor.run(self._load_gantt_data(code, gantt_frame))

    def handle_device_click(self, device_code: str, device_name: str) -> None:
        """Handle device click from UI."""
        logger.info(f"Device clicked: {device_code} ({device_name})")
        if not self._device_service:
            logger.warning("DeviceService không khả dụng trong MainController")
            return
        if self._async_executor:
            self._async_executor.run(self._load_device_history(device_code))
        else:
            logger.warning("AsyncExecutor không khả dụng trong MainController")

    async def _load_device_history(self, device_code: str) -> None:
        """Load history data for selected device."""
        try:
            if not self._device_service:
                logger.error("DeviceService not available in MainController")
                return
            segments = await self._device_service.get_gantt_segments(
                equipment_code=device_code,
                start_time=None,
                end_time=None,
                fill_gaps=True,
            )
            logger.info(f"[History] Loaded {len(segments)} segments for {device_code}")
            if not segments:
                logger.warning(f"[History] No segments found for {device_code}")
                return

            # Delegate conversion to Presenter
            converted_segments = []
            if self._gantt_presenter:
                converted_segments = self._gantt_presenter.convert_to_tuples(segments)
            else:
                # Fallback logic if presenter missing
                for seg in segments:
                    if hasattr(seg, "start_time") and hasattr(seg, "end_time"):
                        converted_segments.append((seg.start_time, seg.end_time, getattr(seg, "status_code", "unknown")))

            current_page = self._view.get_current_page() if self._view else "daboard_page"
            frame_name = self._get_gantt_frame_for_page(current_page)
            if self._gantt_mgr:
                self._gantt_mgr.set_device_data(frame_name, device_code, converted_segments, None, None)
                logger.debug(f"[History] Gantt data updated via Manager for {device_code}")
            elif self._view and hasattr(self._view, "show_gantt_chart"):
                self._view.show_gantt_chart(frame_name, converted_segments)
            else:
                logger.warning("MainView does not support Gantt chart display")
        except Exception as e:
            logger.error(f"Error loading history for {device_code}: {e}", exc_info=True)

    def _get_gantt_frame_for_page(self, page_name: str) -> Optional[str]:
        """Get gantt frame name for page."""
        mapping = {
            "daboard_page": "daboard_midle_frame_2",
            "orders_page": "orders_midle_frame_2",
        }
        return mapping.get(page_name)

    def _on_gantt_segment_clicked(self, frame_name: str, segment: Any) -> None:
        """Handle gantt segment click."""
        logger.debug(f"[MainController] Gantt segment clicked in {frame_name}")

    async def _load_gantt_data(self, device_code: str, frame_name: str) -> None:
        """Load gantt data for device."""
        if not self._device_service or not self._gantt_mgr:
            return
        try:
            logger.debug(f"[MainController] Loading gantt for {device_code}")
            gantt_result = await self._device_service.generate_gantt_segments(device_code, days=1)
            if gantt_result:
                raw_segments = gantt_result.get("segments", [])
                start = gantt_result.get("start")
                end = gantt_result.get("end")

                # Delegate conversion to Presenter
                segments = []
                if self._gantt_presenter:
                    segments = self._gantt_presenter.convert_to_tuples(raw_segments)
                else:
                    # Fallback
                    for seg in raw_segments:
                        if hasattr(seg, "start_time") and hasattr(seg, "end_time"):
                            segments.append((seg.start_time, seg.end_time, getattr(seg, "status_code", "unknown")))

                if segments:
                    self._gantt_mgr.set_device_data(frame_name, device_code, segments, start, end)
                    self.gantt_data_ready.emit(device_code, segments, start, end)
                    logger.debug(f"[MainController] Gantt loaded for {device_code}: {len(segments)} segments")
                else:
                    logger.warning(f"[MainController] No valid segments for {device_code}")
        except Exception as e:
            logger.error(f"[MainController] Gantt load failed: {e}")

    def handle_theme_change(self, mode: str) -> None:
        """Handle theme change request."""
        logger.info(f"[MainController] Theme change: {mode}")
        self._current_mode = mode
        if self._device_layout_mgr:
            self._device_layout_mgr.set_theme(mode)
            device_frames = self._get_frames_by_type("device")
            for frame_name in device_frames:
                svg_path = self._get_frame_svg_path(frame_name, mode)
                if svg_path:
                    self._device_layout_mgr.load_svg_for_frame(frame_name, svg_path)
        if self._gantt_mgr:
            self._gantt_mgr.set_theme(mode)
        if self._legend_mgr:
            self._legend_mgr.set_theme(mode)
        if self._settings_manager:
            self._settings_manager.theme = mode
        self.theme_changed.emit(mode)

    def toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        new_mode = "dark" if self._current_mode == "light" else "light"
        self.handle_theme_change(new_mode)

    async def refresh_all_devices(self) -> None:
        """Refresh all device statuses."""
        if not self._device_service:
            return
        try:
            statuses = await self._device_service.get_all_latest_status()
            if not statuses:
                logger.warning("[MainController] No statuses to refresh")
                return

            status_list = []
            for code, status in statuses.items():
                if hasattr(status, "to_dict"):
                    status_list.append(status.to_dict())
                elif isinstance(status, dict):
                    status_list.append(status)
                else:
                    status_list.append(
                        {
                            "equip_code": code,
                            "status_code": getattr(status, "status_code", "0"),
                        }
                    )

            # FIX: Fetch input and output data for tooltip
            input_list = []
            output_list = []
            if hasattr(self._device_service, "get_all_latest_input"):
                try:
                    inputs = await self._device_service.get_all_latest_input()
                    if inputs:
                        for code, inp in inputs.items():
                            if hasattr(inp, "to_dict"):
                                input_list.append(inp.to_dict())
                            elif isinstance(inp, dict):
                                input_list.append(inp)
                except Exception as e:
                    logger.warning(f"[MainController] Failed to fetch inputs: {e}")

            if hasattr(self._device_service, "get_all_latest_output"):
                try:
                    outputs = await self._device_service.get_all_latest_output()
                    if outputs:
                        for code, out in outputs.items():
                            if hasattr(out, "to_dict"):
                                output_list.append(out.to_dict())
                            elif isinstance(out, dict):
                                output_list.append(out)
                except Exception as e:
                    logger.warning(f"[MainController] Failed to fetch outputs: {e}")

            self.update_device_cache(statuses=status_list, inputs=input_list, outputs=output_list)

            if self._device_layout_mgr:
                status_map = self._convert_to_status_map(status_list)
                self._device_layout_mgr.update_all_status(status_map)
            self.device_status_updated.emit({"statuses": status_list})
        except Exception as e:
            logger.error(f"[MainController] Refresh failed: {e}")

    @staticmethod
    def _convert_to_status_map(statuses: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Convert list of status dicts to status code map.

        Args:
            statuses: List of status dictionaries

        Returns:
            Dictionary mapping device codes to status codes
        """
        result = {}
        for status in statuses:
            code = status.get("EQUIP_CODE") or status.get("equip_code") or status.get("device_id") or status.get("device_id")
            if code:
                result[code] = status.get("equip_status") or status.get("status_code") or status.get("status") or "0"
        return result

    def _on_device_timer(self) -> None:
        """Handle device update timer."""
        if self._device_layout_mgr:
            self._device_layout_mgr.refresh_all_widgets()

    def schedule_device_update(self) -> None:
        """Schedule device position update."""
        if not self._device_update_timer.isActive():
            self._device_update_timer.start()

    def shutdown(self) -> None:
        """Shutdown controller and cleanup."""
        logger.info("[MainController] Shutting down...")
        self._device_update_timer.stop()
        self._device_status_cache.clear()
        self._device_input_cache.clear()
        self._device_output_cache.clear()
        self._initialized = False
        logger.info("[MainController] Shutdown complete")

    def _format_status_display(self, status: Any) -> str:
        """
        Helper to format status code for display.
        Use Application layer UI mapper instead of Domain Enum.
        """
        from iFactory.application.services.status_ui_mapper import StatusUIMapper
        status_code = str(status) if status is not None else "0"
        return StatusUIMapper.get_display_text(status_code)


__all__ = ["MainController"]
