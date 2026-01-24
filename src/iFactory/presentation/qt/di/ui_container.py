"""UI Dependency Injection Container - Optimized with Deferred Loading."""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication
from iFactory.presentation.adapters import QtSignalAdapter, AsyncExecutor
from iFactory.shared.utils.profiler import (
    profile_block,
    profile_method,
    profile_async_method,
    startup_profiler,
)
from iFactory.config import THEME_BASE_PATH, THEME_VARS_PATH, ThemeMode, APP_TITLE

if TYPE_CHECKING:
    from iFactory.application.services.__init__ import DeviceDataService
    from iFactory.config import SettingsManager
    from iFactory.infrastructure.configuration.device_config_loader import (
        DeviceConfigLoader,
    )
    from iFactory.presentation.qt.widgets.factories.timeline_segment_factory import (
        TimelineSegmentFactory,
    )
    from iFactory.presentation.managers.widgets.legend.manager import (
        StatusLegendProvider,
    )
    from iFactory.infrastructure.persistence.services import SyncService
logger = logging.getLogger(__name__)


class UIContainer(QObject):
    """
    UI Dependency Injection Container with Deferred Loading.

    Window shows immediately with cached/skeleton state.
    Fresh data loads in background after window is visible.
    """

    initialization_complete = Signal()
    shutdown_complete = Signal()
    error_occurred = Signal(str)
    theme_changed = Signal(str)
    data_loading_started = Signal()
    data_loading_complete = Signal()

    def __init__(
        self,
        device_service: Optional["DeviceDataService"] = None,
        settings: Optional["SettingsManager"] = None,
        signal_adapter: Optional["QtSignalAdapter"] = None,
        sync_service: Optional["SyncService"] = None,
        parent: Optional[QObject] = None,
    ):
        """Initialize UI container."""
        super().__init__(parent)
        startup_profiler.checkpoint("UIContainer.__init__ start")
        self._device_service = device_service
        self._settings = settings
        self._signal_adapter = signal_adapter or QtSignalAdapter(self)
        self._sync_service = sync_service
        self._async_executor = AsyncExecutor(parent=self)
        self._theme_manager = None
        self._icon_manager = None
        self._device_layout_mgr: Optional["DeviceConfigLoader"] = None
        self._gantt_mgr: Optional["TimelineSegmentFactory"] = None
        self._legend_mgr: Optional["StatusLegendProvider"] = None
        self._main_controller = None
        self._device_controller = None
        self._navigation_controller = None
        self._device_presenter = None
        self._gantt_presenter = None
        self._view = None
        self._device_factory = None
        self._device_config_loader = None
        self._current_theme = ThemeMode.LIGHT
        self._initialized = False
        self._destroyed = False
        self._data_loaded = False
        self._deferred_task: Optional[asyncio.Task] = None
        startup_profiler.checkpoint("UIContainer.__init__ end")
        logger.info("[UIContainer] Created")

    @profile_method(threshold_ms=100)
    def create_main_window(self):
        """Create and wire main window - FAST, no data loading."""
        logger.info("[UIContainer] Creating main window...")
        startup_profiler.checkpoint("create_main_window start")
        try:
            with profile_block("Step 1: Init managers"):
                self._init_managers()
            startup_profiler.checkpoint("Managers initialized")
            with profile_block("Step 2: Create infrastructure managers"):
                self._create_infrastructure_managers()
            startup_profiler.checkpoint("Infrastructure managers created")
            with profile_block("Step 3: Create presenters"):
                self._create_presenters()
            startup_profiler.checkpoint("Presenters created")
            with profile_block("Step 4: Create view"):
                self._create_view()
            startup_profiler.checkpoint("View created")
            with profile_block("Step 5: Create controllers"):
                self._create_controllers()
            startup_profiler.checkpoint("Controllers created")
            with profile_block("Step 6: Inject infrastructure"):
                self._inject_infrastructure_managers()
            startup_profiler.checkpoint("Infrastructure injected")
            with profile_block("Step 7: Wire components"):
                self._wire_components()
            startup_profiler.checkpoint("Components wired")
            with profile_block("Step 8: Apply initial state"):
                self._apply_initial_state()
            startup_profiler.checkpoint("Initial state applied")
            with profile_block("Step 9: Create device widgets"):
                self._create_device_widgets()
            startup_profiler.checkpoint("Device widgets created")
            self._initialized = True
            self.initialization_complete.emit()
            startup_profiler.checkpoint("create_main_window complete")
            logger.info("[UIContainer] Main window created successfully")
            return self._view
        except Exception as e:
            logger.exception(f"[UIContainer] Creation failed: {e}")
            startup_profiler.checkpoint(f"FAILED: {e}")
            self.error_occurred.emit(str(e))
            raise

    @profile_async_method(threshold_ms=100)
    async def initialize_async(self) -> None:
        """
        Initialize async components - FAST.

        Only does minimal setup. Heavy data loading is deferred.
        """
        startup_profiler.checkpoint("UIContainer.initialize_async start")
        with profile_block("MainController.initialize"):
            if self._main_controller and hasattr(self._main_controller, "initialize"):
                await self._main_controller.initialize()
        startup_profiler.checkpoint("UIContainer.initialize_async complete")
        logger.info("[UIContainer] Async init complete (data loading deferred)")

    def schedule_deferred_data_load(self) -> None:
        """
        Schedule data loading to run after window is visible.

        Call this AFTER window.show() has been called.
        """
        if self._data_loaded or self._deferred_task is not None:
            logger.debug("[UIContainer] Deferred load already scheduled/complete")
            return
        logger.info("[UIContainer] Scheduling deferred data load...")
        QTimer.singleShot(100, self._start_deferred_load)

    def _start_deferred_load(self) -> None:
        """Start deferred data loading (called from QTimer)."""
        try:
            loop = asyncio.get_event_loop()
            self._deferred_task = loop.create_task(self._load_data_deferred())
        except RuntimeError:
            logger.warning("[UIContainer] No event loop, using executor")
            self._async_executor.run_async(self._load_data_deferred())

    async def _load_data_deferred(self) -> None:
        """
        Load data in background after window is visible.

        This is heavy operation that was blocking startup.
        """
        if self._data_loaded:
            return
        logger.info("[UIContainer] Starting deferred data load...")
        self.data_loading_started.emit()
        try:
            if self._view and hasattr(self._view, "show_loading_state"):
                self._view.show_loading_state(True, "Loading device data...")
            await asyncio.sleep(0.05)
            with profile_block("Load cached devices"):
                await self._load_cached_devices()
            with profile_block("Refresh from remote"):
                await self._refresh_devices_from_remote()
            self._data_loaded = True
            logger.info("[UIContainer] Deferred data load complete")
        except Exception as e:
            logger.error(f"[UIContainer] Deferred load failed: {e}")
        finally:
            self._deferred_task = None
            self.data_loading_complete.emit()
            if self._view and hasattr(self._view, "show_loading_state"):
                self._view.show_loading_state(False)

    async def _load_cached_devices(self) -> None:
        """Load devices from local cache (fast)."""
        if not self._device_controller:
            return
        try:
            if hasattr(self._device_controller, "load_from_cache"):
                await self._device_controller.load_from_cache()
                logger.info("[UIContainer] Loaded cached device data")
        except Exception as e:
            logger.debug(f"[UIContainer] No cached data: {e}")

    async def _refresh_devices_from_remote(self) -> None:
        """Refresh devices from remote database."""
        if not self._device_controller:
            return
        try:
            if hasattr(self._device_controller, "refresh_all_devices"):
                await self._device_controller.refresh_all_devices()
                logger.info("[UIContainer] Refreshed from remote")
        except Exception as e:
            logger.warning(f"[UIContainer] Remote refresh failed: {e}")

    def _init_managers(self) -> None:
        """Initialize UI managers."""
        logger.debug("  Initializing managers...")
        with profile_block("ThemeManager creation"):
            if THEME_BASE_PATH.exists() and THEME_VARS_PATH.exists():
                try:
                    from iFactory.presentation.managers import ThemeManager

                    self._theme_manager = ThemeManager(THEME_BASE_PATH, THEME_VARS_PATH)
                    logger.info("ThemeManager initialized")
                except Exception as e:
                    logger.warning(f"ThemeManager failed: {e}")
        with profile_block("IconManager creation"):
            if THEME_VARS_PATH.exists():
                try:
                    from iFactory.presentation.managers import IconManager

                    initial_mode = self._get_saved_theme().value
                    self._icon_manager = IconManager(THEME_VARS_PATH, initial_mode=initial_mode)
                    logger.info(f"IconManager initialized (cache size: 100, mode: {initial_mode})")
                except Exception as e:
                    logger.warning(f"IconManager failed: {e}")

    def _create_infrastructure_managers(self) -> None:
        """Create infrastructure managers."""
        logger.debug("  Creating infrastructure managers...")
        with profile_block("DeviceConfigLoader creation"):
            try:
                from iFactory.infrastructure.configuration.device_config_loader import (
                    DeviceConfigLoader,
                )

                self._device_layout_mgr = DeviceConfigLoader()
            except Exception as e:
                logger.warning(f"DeviceConfigLoader failed: {e}")
        with profile_block("TimelineSegmentFactory creation"):
            try:
                from iFactory.presentation.qt.widgets.factories.timeline_segment_factory import (
                    TimelineSegmentFactory,
                )

                self._gantt_mgr = TimelineSegmentFactory()
            except Exception as e:
                logger.warning(f"TimelineSegmentFactory failed: {e}")
        with profile_block("StatusLegendProvider creation"):
            try:
                # FIXED: Corrected import path to existing module
                from iFactory.presentation.managers.widgets.legend.manager import (
                    StatusLegendProvider,
                )

                self._legend_mgr = StatusLegendProvider()
            except Exception as e:
                logger.warning(f"StatusLegendProvider failed: {e}")
        logger.info(
            f"  [OK] Infrastructure managers created: device={self._device_layout_mgr is not None}, gantt={self._gantt_mgr is not None}, legend={self._legend_mgr is not None}"
        )

    def _create_presenters(self) -> None:
        """Create presenter instances."""
        with profile_block("Presenters creation"):
            try:
                from iFactory.presentation.qt.presenters import (
                    DevicePresenter,
                    GanttPresenter,
                )

                self._device_presenter = DevicePresenter()
                self._gantt_presenter = GanttPresenter()
                logger.debug("    [OK] Presenters created")
            except Exception as e:
                logger.warning(f"    Presenters failed: {e}")

    def _create_view(self) -> None:
        """Create main view."""
        logger.debug("  Creating view...")
        with profile_block("Import MainView"):
            from iFactory.presentation.qt.views import MainView
        with profile_block("MainView instantiation"):
            self._view = MainView(
                theme_manager=self._theme_manager,
                icon_manager=self._icon_manager,
                settings=self._settings,
                db_bridge=self._signal_adapter,
                device_layout_manager=self._device_layout_mgr,
                gantt_manager=self._gantt_mgr,
                legend_manager=self._legend_mgr,
            )
        with profile_block("MainView configuration"):
            self._view.setWindowTitle(APP_TITLE)
            self._view.setMinimumSize(800, 600)
        logger.debug("    [OK] View created")

    def _create_controllers(self) -> None:
        """Create controller instances."""
        logger.debug("  Creating controllers...")
        with profile_block("Controllers import"):
            from iFactory.presentation.qt.controllers import (
                MainController,
                DeviceController,
                NavigationController,
            )
        with profile_block("MainController creation"):
            self._main_controller = MainController(
                device_service=self._device_service,
                async_executor=self._async_executor,
                device_presenter=self._device_presenter,
                gantt_presenter=self._gantt_presenter,
                parent=self,
            )
        with profile_block("DeviceController creation"):
            self._device_controller = DeviceController(
                device_service=self._device_service,
                signal_adapter=self._signal_adapter,
                async_executor=self._async_executor,
                sync_service=self._sync_service,
                device_presenter=self._device_presenter,
                parent=self,
            )
        with profile_block("NavigationController creation"):
            page_names = ["daboard_page", "orders_page"]
            default_page = "daboard_page"
            if self._settings:
                default_page = self._settings.default_page
            self._navigation_controller = NavigationController(page_names=page_names, default_page=default_page, parent=self)
        with profile_block("Controller wiring"):
            self._main_controller.set_device_controller(self._device_controller)
            self._main_controller.set_navigation_controller(self._navigation_controller)
        logger.debug("    [OK] Controllers created")

    def _inject_infrastructure_managers(self) -> None:
        """Inject infrastructure managers into MainController."""
        if not self._main_controller:
            return
        with profile_block("Infrastructure injection"):
            self._main_controller.set_view(self._view)
            self._main_controller.set_managers(
                theme=self._theme_manager,
                icon=self._icon_manager,
                settings=self._settings,
            )
            self._main_controller.set_infrastructure_managers(
                device_layout=self._device_layout_mgr,
                gantt=self._gantt_mgr,
                legend=self._legend_mgr,
            )
        logger.debug("    [OK] Infrastructure managers injected")

    def _wire_components(self) -> None:
        """Wire all components together."""
        logger.debug("  Wiring components...")
        if not self._view:
            return
        with profile_block("Signal connections"):
            self._view.page_requested.connect(self._on_page_requested)
            self._view.device_clicked.connect(self._on_device_clicked)
            self._view.theme_toggle_requested.connect(self.toggle_theme)
            self._view.left_menu_toggle_requested.connect(self._on_menu_toggle)
            self._view.right_panel_toggle_requested.connect(self._on_panel_toggle)
            self._view.close_requested.connect(self._on_close_requested)
            if self._navigation_controller:
                self._navigation_controller.page_changed.connect(self._view.navigate_to_page)
            self._signal_adapter.device_statuses_updated.connect(self._on_device_statuses_updated)
            self._signal_adapter.gantt_data_ready.connect(self._on_gantt_data_ready)
            if self._device_service:
                self._signal_adapter.set_gantt_provider(self._device_service)
        logger.debug("    [OK] Components wired")

    def _apply_initial_state(self) -> None:
        """Apply initial UI state."""
        logger.debug("  Applying initial state...")
        with profile_block("Get saved theme"):
            theme_mode = self._get_saved_theme()
        with profile_block("Apply theme stylesheet"):
            self._apply_theme(theme_mode)
        with profile_block("Initial navigation"):
            if self._navigation_controller and self._view:
                initial_page = self._navigation_controller.current_page
                logger.info(f"  [DEBUG] Navigating to initial page: '{initial_page}'")
                success = self._view.navigate_to_page(initial_page)
                logger.info(f"  [DEBUG] Navigation result: {success}")
        logger.debug(f"    [OK] Initial state applied (theme: {theme_mode.value})")

    def _create_device_widgets(self) -> None:
        """Create device widgets."""
        # FIXED: If the DeviceLayoutManager is already set, it handles widget creation
        # internally via register_frame during initialization. This prevents the redundant
        # and failing attempt to import a non-existent DeviceWidgetFactory.
        if self._device_layout_mgr:
            logger.debug("  Device widgets handled by DeviceLayoutManager, skipping redundant creation.")
            return

        if not self._view:
            return
        logger.debug("  Creating device widgets...")
        try:
            with profile_block("Import device widget factory"):
                from iFactory.ui.widgets.device_canvas import (
                    DeviceWidgetFactory as WidgetFactory,
                )
            with profile_block("Load device config"):
                try:
                    from iFactory.config.device_config import DeviceConfigLoader

                    self._device_config_loader = DeviceConfigLoader()
                    self._device_config_loader.load()
                except ImportError:
                    logger.debug("    DeviceConfigLoader not available")
                    self._device_config_loader = None
            with profile_block("Create widget factory"):
                self._device_factory = WidgetFactory(self._icon_manager)
            is_dark = self._current_theme == ThemeMode.DARK
            with profile_block("Load device positions JSON"):
                import json
                from iFactory.config import PATHS

                config_path = PATHS.device_positions_path
                if not config_path.exists():
                    logger.warning(f"  Device positions not found: {config_path}")
                    return
                full_config = json.loads(config_path.read_text(encoding="utf-8"))
            frame_mapping = {
                "daboard_midle_frame_1": "daboard_midle_frame_1",
                "orders_midle_frame_1": "orders_midle_frame_1",
            }
            total_widgets = 0
            with profile_block("Create all device widgets"):
                for frame_key, frame_name in frame_mapping.items():
                    frame_config = full_config.get(frame_key, {})
                    devices = frame_config.get("devices", [])
                    if not devices:
                        continue
                    frame = getattr(self._view.ui, frame_name, None)
                    if not frame:
                        continue
                    for device_cfg in devices:
                        try:
                            widget = self._device_factory.create_from_config(device_cfg, parent=frame, is_dark=is_dark)
                            self._view.register_device_widget(widget.device_code, widget)
                            widget.clicked.connect(self._on_device_widget_clicked)
                            widget.show()
                            total_widgets += 1
                        except Exception as e:
                            logger.warning(f"    Failed to create widget: {e}")
            logger.info(f"  [OK] Created {total_widgets} device widgets")
        except ImportError as e:
            logger.warning(f"  Device widgets not available: {e}")
        except Exception as e:
            logger.error(f"  Device widget creation failed: {e}")

    def _get_saved_theme(self) -> ThemeMode:
        """Get saved theme from settings."""
        if self._settings:
            try:
                return ThemeMode.from_string(self._settings.theme)
            except:
                pass
        return ThemeMode.LIGHT

    def _apply_theme(self, mode: ThemeMode) -> None:
        """Apply theme to application."""
        self._current_theme = mode
        mode_str = mode.value
        with profile_block("Update icon manager theme"):
            if self._icon_manager:
                try:
                    self._icon_manager.set_mode(mode_str)
                except Exception as e:
                    logger.warning(f"IconManager update failed: {e}")
        with profile_block("Update device factory themes"):
            if self._device_factory:
                is_dark = mode == ThemeMode.DARK
                self._device_factory.update_all_themes(is_dark)
        with profile_block("Update infrastructure manager themes"):
            if self._device_layout_mgr:
                self._device_layout_mgr.set_theme(mode_str)
            if self._gantt_mgr:
                self._gantt_mgr.set_theme(mode_str)
            if self._legend_mgr:
                self._legend_mgr.set_theme(mode_str)
        with profile_block("Render and apply stylesheet"):
            if self._theme_manager and self._view:
                stylesheet = self._theme_manager.set_theme(mode_str)
                self._view.apply_theme(mode_str, stylesheet)

    def set_theme(self, mode: str) -> None:
        """Set application theme."""
        theme_mode = ThemeMode.from_string(mode)
        self._apply_theme(theme_mode)
        if self._settings:
            try:
                self._settings.theme = mode
            except Exception as e:
                logger.warning(f"Failed to save theme: {e}")
        self.theme_changed.emit(mode)

    def toggle_theme(self) -> str:
        """Toggle between light and dark theme."""
        new_mode = ThemeMode.DARK if self._current_theme == ThemeMode.LIGHT else ThemeMode.LIGHT
        self.set_theme(new_mode.value)
        return new_mode.value

    @property
    def current_theme(self) -> str:
        """Get current theme."""
        return self._current_theme.value

    def _on_device_widget_clicked(self, device_code: str, device_name: str) -> None:
        """Handle device widget click."""
        self._view.device_clicked.emit(device_code, device_name)

    def _on_page_requested(self, page_name: str) -> None:
        """Handle page navigation."""
        if self._navigation_controller:
            self._navigation_controller.navigate_to(page_name)

    def _on_device_clicked(self, device_code: str, device_name: str) -> None:
        """Handle device click."""
        if self._main_controller and (not self._destroyed):
            self._main_controller.handle_device_click(device_code, device_name)

    def _on_menu_toggle(self) -> None:
        """Handle menu toggle."""
        if self._view:
            current = self._view.is_left_menu_expanded()
            self._view.set_left_menu_expanded(not current)

    def _on_panel_toggle(self) -> None:
        """Handle panel toggle."""
        if self._view:
            current = self._view.is_right_panel_visible()
            self._view.set_right_panel_visible(not current)

    def _on_close_requested(self) -> None:
        """Handle close request."""
        logger.info("[UIContainer] Close requested")
        self.cleanup()

    def _on_device_statuses_updated(self, statuses: dict) -> None:
        """Handle device statuses update."""
        if not self._view or self._destroyed:
            return
        if not statuses:
            return
        if self._main_controller:
            try:
                status_list = []
                for code, data in statuses.items():
                    item = {}
                    if hasattr(data, "to_dict"):
                        item = data.to_dict()
                    elif isinstance(data, dict):
                        item = data
                    else:
                        item = {
                            "equip_code": code,
                            "status_code": getattr(data, "status_code", "0"),
                        }
                    status_list.append(item)
                self._main_controller.update_device_cache(statuses=status_list)
                logger.debug(f"[UIContainer] MainController cache updated with {len(status_list)} items")
            except Exception as e:
                logger.error(f"[UIContainer] Failed to update MainController cache: {e}")
        if self._device_presenter:
            try:
                presentation_data = self._device_presenter.present_device_list(statuses)
                status_list = []
                for code, vm in presentation_data.items():
                    status_list.append(
                        {
                            "EQUIP_CODE": code,
                            "equip_code": code,
                            "EQUIP_STATUS": vm.status_code,
                            "status_code": vm.status_code,
                            "status_color": vm.status_color,
                            "status_display": vm.status_display,
                        }
                    )
                if hasattr(self._view, "update_device_statuses"):
                    self._view.update_device_statuses(status_list)
                elif hasattr(self._view, "update_all_device_statuses"):
                    self._view.update_all_device_statuses(presentation_data)
            except Exception as e:
                logger.error(f"[UIContainer] Presenter formatting failed: {e}")
        if self._device_factory:
            try:
                self._device_factory.update_all_statuses(statuses)
            except Exception as e:
                logger.error(f"[UIContainer] Widget update failed: {e}")

    def _on_gantt_data_ready(self, device_code: str, segments: list, start, end) -> None:
        """Handle Gantt data ready."""
        if not self._view or self._destroyed:
            return
        if self._gantt_presenter:
            try:
                formatted_segments = []
                for seg in segments:
                    if hasattr(seg, "start_time") and hasattr(seg, "end_time"):
                        formatted_segments.append(
                            (
                                seg.start_time,
                                seg.end_time,
                                getattr(seg, "status_code", "unknown"),
                            )
                        )
                    elif isinstance(seg, dict):
                        seg_start = seg.get("start_time") or seg.get("start")
                        seg_end = seg.get("end_time") or seg.get("end")
                        status = seg.get("status") or seg.get("status_code", "unknown")
                        formatted_segments.append((seg_start, seg_end, status))
                    elif isinstance(seg, (list, tuple)) and len(seg) >= 3:
                        formatted_segments.append(tuple(seg[:3]))
                segments_data = self._gantt_presenter.format_segments(formatted_segments, start, end)
                chart_vm = self._gantt_presenter.format_chart(device_code, formatted_segments, start, end)
                current_page = self._view.get_current_page()
                frame_name = self._get_gantt_frame(current_page)
                self._view.show_gantt_chart(frame_name, segments_data, chart_vm)
            except Exception as e:
                logger.error(f"[UIContainer] Gantt formatting failed: {e}")

    def _get_gantt_frame(self, page_name: str) -> str:
        """Map page to gantt frame."""
        mapping = {
            "daboard_page": "daboard_midle_frame_2",
            "orders_page": "orders_midle_frame_2",
        }
        return mapping.get(page_name, "daboard_midle_frame_2")

    def get_main_controller(self):
        return self._main_controller

    def get_device_controller(self):
        return self._device_controller

    def get_view(self):
        return self._view

    def get_main_view(self):
        return self._view

    def get_device_layout_manager(self) -> Optional["DeviceConfigLoader"]:
        return self._device_layout_mgr

    def get_gantt_manager(self) -> Optional["TimelineSegmentFactory"]:
        return self._gantt_mgr

    def get_legend_manager(self) -> Optional["StatusLegendProvider"]:
        return self._legend_mgr

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def is_data_loaded(self) -> bool:
        """Check if deferred data has been loaded."""
        return self._data_loaded

    def cleanup(self) -> None:
        """Cleanup UI container."""
        if self._destroyed:
            return
        logger.info("[UIContainer] Cleaning up...")
        self._destroyed = True
        if self._deferred_task and (not self._deferred_task.done()):
            self._deferred_task.cancel()
        self._async_executor.cancel_all_periodic()
        if self._main_controller and hasattr(self._main_controller, "shutdown"):
            self._main_controller.shutdown()
        if self._icon_manager:
            try:
                self._icon_manager.clear_cache()
            except:
                pass
        if self._legend_mgr and hasattr(self._legend_mgr, "dispose"):
            try:
                self._legend_mgr.dispose()
            except:
                pass
        self._signal_adapter.clear_cache()
        self.shutdown_complete.emit()
        logger.info("[UIContainer] Cleanup complete")

    async def shutdown_async(self) -> None:
        """Async shutdown."""
        await self._async_executor.shutdown()
        self.cleanup()


__all__ = ["UIContainer", "AsyncExecutor", "QtSignalAdapter"]
