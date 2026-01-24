"""
Main View - Optimized for Fast Startup.

Refactored:
- Fixed NameError by importing 'date'.
- Removed fallback manager creation to prevent duplicate UI rendering.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, replace
from functools import cached_property
from datetime import datetime, date
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Tuple,
    Type,
)
from PySide6.QtCore import Signal, Qt, QTimer, QPoint, QRect, QSignalBlocker
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow,
    QFrame,
    QWidget,
    QApplication,
    QMessageBox,
    QVBoxLayout,
)
from iFactory.presentation.managers.ui.generated.main_ui import Ui_MainWindow
from iFactory.presentation.managers.widgets.constants import (
    WindowConstants,
    PAGE_MAPPING,
    DEVICE_FRAMES_LIST,
    GANTT_FRAMES_LIST,
    LEGEND_FRAMES_LIST,
    Icons,
    Shortcuts,
    HistoryType,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QListWidgetItem
    from iFactory.presentation.managers import IconManager, ThemeManager
    from iFactory.infrastructure.configuration.device_config_loader import (
        DeviceLayoutManager,
    )
    from iFactory.infrastructure.factories.timeline_segment_factory import GanttManager
    from iFactory.infrastructure.configuration.legend.manager import LegendManager
logger = logging.getLogger(__name__)
TooltipProvider = Callable[[str], Dict[str, Any]]
ContextMenuProvider = Callable[[str, str, QPoint], None]
try:
    from iFactory.shared.utils.profiler import profile_block, startup_profiler
except ImportError:
    from contextlib import nullcontext

    def profile_block(_: str):
        return nullcontext()

    class _DummyProfiler:

        def checkpoint(self, _: str) -> None:
            pass

    startup_profiler = _DummyProfiler()


@dataclass(frozen=True, slots=True)
class MenuItem:
    """Menu item configuration."""

    title: str
    icon: str
    shortcut: str = ""


DEFAULT_MENU_ITEMS: Final[Tuple[MenuItem, ...]] = (
    MenuItem("Dashboard", ":/icon/dashboard.svg", "Ctrl+1"),
    MenuItem("Orders", ":/icon/orders.svg", "Ctrl+2"),
    MenuItem("Products", ":/icon/products.svg", "Ctrl+3"),
    MenuItem("Customers", ":/icon/customers.svg", "Ctrl+4"),
    MenuItem("Reports", ":/icon/reports.svg", "Ctrl+5"),
)


@dataclass(frozen=True, slots=True)
class ViewState:
    """Immutable view state container."""

    current_page: str = "daboard_page"
    theme_mode: str = "light"
    left_menu_expanded: bool = False
    right_panel_visible: bool = False
    selected_device: Optional[str] = None

    def with_page(self, page: str) -> ViewState:
        return replace(self, current_page=page)

    def with_theme(self, mode: str) -> ViewState:
        return replace(self, theme_mode=mode)

    def with_menu_expanded(self, expanded: bool) -> ViewState:
        return replace(self, left_menu_expanded=expanded)


class _LazyImports:
    """Cached lazy imports to avoid repeated module loading."""

    @cached_property
    def MenuManager(self) -> Type:
        from iFactory.presentation.managers.ui_managers import MenuManager

        return MenuManager

    @cached_property
    def AnimationManager(self) -> Tuple[Type, Type]:
        from iFactory.presentation.managers.ui_managers import (
            AnimationManager,
            AnimationTarget,
        )

        return (AnimationManager, AnimationTarget)

    @cached_property
    def PanelManager(self) -> Type:
        from iFactory.presentation.managers.ui_managers import PanelManager

        return PanelManager

    @cached_property
    def RightPanelManager(self) -> Type:
        from iFactory.presentation.managers.ui_managers import RightPanelManager

        return RightPanelManager

    @cached_property
    def ShortcutManager(self) -> Tuple[Type, Callable]:
        from iFactory.presentation.managers.ui_managers import (
            ShortcutManager,
            create_standard_shortcuts,
        )

        return (ShortcutManager, create_standard_shortcuts)


_imports = _LazyImports()


class MainView(QMainWindow):
    """
    Main View with Full Manager Integration and Deferred Theme Loading.
    """

    page_requested = Signal(str)
    menu_item_clicked = Signal(int)
    device_clicked = Signal(str, str)
    device_history_requested = Signal(str, str)
    right_panel_toggle_requested = Signal()
    left_menu_toggle_requested = Signal()
    theme_toggle_requested = Signal()
    theme_changed = Signal(str)
    close_requested = Signal()

    def __init__(
        self,
        theme_manager: ThemeManager,
        icon_manager: IconManager,
        settings: Any = None,
        db_bridge: Any = None,
        device_layout_manager: Optional[DeviceLayoutManager] = None,
        gantt_manager: Optional[GanttManager] = None,
        legend_manager: Optional[LegendManager] = None,
        parent: Optional[QMainWindow] = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme_manager
        self._icons = icon_manager
        self._settings = settings
        self._db_bridge = db_bridge
        # FIX: Store injected managers directly. We do NOT create fallback instances anymore.
        self._injected_managers = {
            "device": device_layout_manager,
            "gantt": gantt_manager,
            "legend": legend_manager,
        }
        self._init_done = False
        self._destroyed = False
        self._theme_applied = False
        self._first_show_done = False
        self.setUpdatesEnabled(False)
        try:
            self._init_state()
            self._setup_ui()
            self._init_managers()
            self._setup_connections()
            self._apply_initial_state()
            self._connect_db_bridge()
        finally:
            self.setUpdatesEnabled(True)
        self._init_done = True
        startup_profiler.checkpoint("MainView.__init__ end")

    def _init_state(self) -> None:
        """Initialize internal state."""
        initial_mode = getattr(self._settings, "theme", None) or "light"
        self._state = ViewState(theme_mode=initial_mode)
        self._was_maximized = False
        self._constants = WindowConstants()
        self._current_history_device: Optional[str] = None
        self._current_history_type: Optional[str] = None
        self._device_widgets: Dict[str, Any] = {}
        self._tooltip_provider: Optional[TooltipProvider] = None
        self._context_menu_provider: Optional[ContextMenuProvider] = None
        self._menu_mgr = None
        self._anim_mgr = None
        self._panel_mgr = None
        self._right_mgr = None
        self._shortcut_mgr = None
        self._device_mgr = None

    def _setup_ui(self) -> None:
        """Setup UI from designer file."""
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("iFactory")
        self._set_window_icon()

    def _set_window_icon(self) -> None:
        """Set window icon."""
        if not (icon := QIcon(Icons.LOGO)).isNull():
            self.setWindowIcon(icon)
            if app := QApplication.instance():
                app.setWindowIcon(icon)

    def _init_managers(self) -> None:
        """Initialize all UI managers."""
        self._init_menu_manager()
        self._init_animation_manager()
        self._init_panel_manager()
        self._init_right_panel_manager()
        self._init_shortcut_manager()
        self._init_device_manager()
        self._setup_header()
        self._setup_timers()

    def _init_menu_manager(self) -> None:
        self._menu_mgr = _imports.MenuManager(
            self.ui.listWidget,
            self.ui.listWidget_settings,
            self._icons,
            self._constants,
        )
        self._menu_mgr.set_menu_items(list(DEFAULT_MENU_ITEMS), PAGE_MAPPING)
        self._menu_mgr.add_settings_item(Icons.SETTINGS, "Settings", "Ctrl+,")

    def _init_animation_manager(self) -> None:
        (AnimationManager, AnimationTarget) = _imports.AnimationManager
        self._anim_mgr = AnimationManager(self._constants)
        self._anim_target = AnimationTarget
        self._anim_mgr.set_callbacks(
            AnimationTarget.LEFT_MENU,
            min_callback=lambda v: self.ui.left_slide_menu_frame.setMinimumWidth(int(v)),
            max_callback=self._on_left_menu_max_changed,
            finished_callback=self._on_animation_finished,
        )
        self._anim_mgr.set_callbacks(
            AnimationTarget.RIGHT_PANEL,
            min_callback=lambda v: self.ui.right_slide_menu_frame.setMinimumWidth(int(v)),
            max_callback=lambda v: self.ui.right_slide_menu_frame.setMaximumWidth(int(v)),
            finished_callback=self._on_animation_finished,
        )

    def _on_left_menu_max_changed(self, value: int) -> None:
        self.ui.left_slide_menu_frame.setMaximumWidth(int(value))
        if self._init_done and self._panel_mgr and self._panel_mgr.any_visible():
            self._schedule_position_update()

    def _on_animation_finished(self) -> None:
        if not self._destroyed and self._device_mgr:
            self._device_mgr.refresh_all_widgets()

    def _init_panel_manager(self) -> None:
        self._panel_mgr = _imports.PanelManager(self.ui.centralwidget, self._icons, self._constants)
        sp = self._panel_mgr.settings_panel
        sp.btn_theme.set_click_callback(self._on_theme_button_clicked)
        sp.btn_info.set_click_callback(self._show_info)
        tp = self._panel_mgr.theme_panel
        tp.btn_light.set_click_callback(lambda: self._apply_theme("light"))
        tp.btn_dark.set_click_callback(lambda: self._apply_theme("dark"))
        self._panel_mgr.click_catcher.clicked.connect(self._on_click_outside)
        self._panel_mgr.set_rect_providers(
            settings_rect=self._get_settings_item_rect,
            left_menu_rect=lambda: self.ui.left_slide_menu_frame.geometry(),
        )
        self._panel_mgr.set_position_callback(self._panel_mgr.update_positions)

    def _init_right_panel_manager(self) -> None:
        self._right_mgr = _imports.RightPanelManager(
            self.ui.right_slide_menu_frame,
            self.ui.centralwidget,
            self._icons,
            self._constants,
        )
        self._right_mgr.set_close_callback(lambda: self._set_right_menu(False, animate=True))
        self._right_mgr.set_data_request_callback(self._on_right_menu_data_request)

    def _init_shortcut_manager(self) -> None:
        (ShortcutManager, create_shortcuts) = _imports.ShortcutManager
        self._shortcut_mgr = ShortcutManager(self)
        create_shortcuts(
            self._shortcut_mgr,
            {
                "escape": self._on_escape,
                "fullscreen": self._toggle_fullscreen,
                "info": self._show_info,
                "next_page": self._next_page,
                "prev_page": self._prev_page,
                "go_to_page": self._go_to_page,
                "toggle_theme": self._toggle_theme,
                "toggle_left_menu": self._toggle_left_menu,
                "toggle_right_menu": self._toggle_right_menu,
                "toggle_settings": self._panel_mgr.toggle_settings,
                "toggle_edit_mode": self._toggle_edit_mode,
            },
        )

    def _init_device_manager(self) -> None:
        """
        Initialize device integration manager.

        FIX: Removed fallback creation logic.
        If self._injected_managers["device"] is None, we log and exit.
        This prevents duplicate UI rendering caused by View creating its own manager
        while Controller injects another one.
        """
        self._device_mgr = self._injected_managers["device"]
        if not self._device_mgr:
            logger.warning("[MainView] DeviceLayoutManager is None. Skipping device init.")
            return

        mode = self._state.theme_mode
        frames = {
            "device": self._get_frame_dict(DEVICE_FRAMES_LIST),
            "gantt": self._get_frame_dict(GANTT_FRAMES_LIST),
            "legend": self._get_frame_dict(LEGEND_FRAMES_LIST),
        }
        for frame in frames["device"].values():
            if frame:
                self._clear_frame_layout(frame)
        for name, frame in frames["device"].items():
            if frame:
                try:
                    # FIX: Only register if manager exists
                    self._device_mgr.register_frame(name, frame)
                except Exception as e:
                    logger.error(f"Failed to register device frame {name}: {e}")

        # Setup Gantt
        gantt_mgr = self._injected_managers["gantt"]
        if gantt_mgr:
            for name, frame in frames["gantt"].items():
                if frame:
                    self._clear_frame_layout(frame)
                    if hasattr(gantt_mgr, "register_frame"):
                        gantt_mgr.register_frame(name, frame)

        # Setup Legend
        legend_mgr = self._injected_managers["legend"]
        if legend_mgr:
            for name, frame in frames["legend"].items():
                if frame:
                    self._clear_frame_layout(frame)
                    legend_mgr.register_frame(name, frame)

        self._device_mgr.set_theme(mode)
        if gantt_mgr:
            gantt_mgr.set_theme(mode)
        if legend_mgr:
            legend_mgr.set_theme(mode)

        self._device_mgr.set_click_callback(self._on_device_clicked)
        self._device_mgr.set_context_menu_callback(self._on_context_menu_requested)

    def _get_frame_dict(self, names: List[str]) -> Dict[str, Optional[QFrame]]:
        return {name: getattr(self.ui, name, None) for name in names}

    @staticmethod
    def _clear_frame_layout(frame: QFrame) -> None:
        """Clear layout and widgets properly."""
        if not frame:
            return
        if layout := frame.layout():
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                if child := item.layout():
                    self._clear_frame_layout(child)
        else:
            frame.setLayout(QVBoxLayout())

    def _setup_header(self) -> None:
        """Setup header elements."""
        ti = self.ui.title_icon
        ti.setText("")
        ti.setPixmap(QPixmap(Icons.LOGO))
        ti.setScaledContents(True)
        ti.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.title_label.setText("Welcome to iFactory")
        self.ui.title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        btn = self.ui.pushButton
        btn.setObjectName("menu_btn")
        btn.setText("")
        btn.setCheckable(True)
        btn.setIconSize(self._constants.ICON_SIZE)
        for frame in (
            self.ui.title_frame,
            self.ui.left_slide_menu_frame,
            self.ui.right_slide_menu_frame,
        ):
            frame.setFrameShape(QFrame.Shape.NoFrame)
            frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def _setup_timers(self) -> None:
        """Setup internal timers."""
        self._position_timer = QTimer(self)
        self._position_timer.setSingleShot(True)
        self._position_timer.setInterval(self._constants.TIMER_POSITION_UPDATE)
        self._position_timer.timeout.connect(self._do_position_update)
        self._device_timer = QTimer(self)
        self._device_timer.setSingleShot(True)
        self._device_timer.setInterval(self._constants.TIMER_DEVICE_UPDATE)
        self._device_timer.timeout.connect(self._update_device_positions)

    def _update_device_positions(self) -> None:
        if not self._destroyed and self._device_mgr:
            self._device_mgr.refresh_all_widgets()

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self.ui.pushButton.toggled.connect(lambda checked: self._set_left_menu(checked, animate=True))
        self.ui.listWidget.itemClicked.connect(self._on_menu_item_clicked)
        self.ui.listWidget_settings.itemClicked.connect(self._on_settings_clicked)
        self.ui.stackedWidget.currentChanged.connect(self._on_page_changed)

    def set_controller(self, controller: Any) -> None:
        """Set controller and wire signals."""
        self._controller = controller
        if hasattr(self._controller, "right_panel_data_ready"):
            self._controller.right_panel_data_ready.connect(self._on_right_panel_data_ready)
            logger.debug("[MainView] Connected to MainController.right_panel_data_ready")
        if hasattr(self._controller, "_get_device_tooltip_data"):
            self.set_tooltip_provider(self._controller._get_device_tooltip_data)
        if hasattr(self._controller, "_show_device_context_menu"):
            self.set_context_menu_provider(self._controller._show_device_context_menu)

    def _on_right_panel_data_ready(self, data: Dict[str, Any]) -> None:
        """Handle data ready from controller for Right Panel."""
        dtype = data.get("type")
        device = data.get("device")
        if dtype == "history":
            history_type = data.get("history_type", "status")
            self._current_history_device = device
            self._current_history_type = history_type
            self._set_right_menu(True, animate=True)
            if self._right_mgr:
                self._right_mgr.menu_widget.start_loading("Loading...")

                # FIX: Handle date object correctly
                # _date_edit.date().toPython() returns a date object
                try:
                    days = self._right_mgr.menu_widget._date_edit.date().toPython()
                    if isinstance(days, date):
                        days = 1
                except:
                    days = 1

                self._request_device_history(device, history_type, days)

    def _apply_initial_state(self) -> None:
        """Apply initial UI state (theme deferred to showEvent)."""
        with QSignalBlocker(self.ui.pushButton):
            self.ui.pushButton.setChecked(False)
        self._set_left_menu(False, animate=False)
        self._set_right_menu(False, animate=False)
        self.ui.stackedWidget.setCurrentWidget(self.ui.daboard_page)

    def _connect_db_bridge(self) -> None:
        """Connect database bridge signals."""
        if not self._db_bridge:
            return
        signals = {
            "gantt_data_ready": self._on_gantt_data_ready,
            "table_data_ready": self._on_table_data_ready,
            "summary_data_ready": self._on_summary_data_ready,
        }
        for name, handler in signals.items():
            if hasattr(self._db_bridge, name):
                getattr(self._db_bridge, name).connect(handler)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._first_show_done:
            self._first_show_done = True
            QTimer.singleShot(0, self._on_first_show)

    def _on_first_show(self) -> None:
        """Deferred initialization after first show."""
        if self._destroyed:
            return
        self._apply_theme(self._state.theme_mode)
        gantt_mgr = self._injected_managers["gantt"]
        if gantt_mgr and hasattr(gantt_mgr, "init_data"):
            QTimer.singleShot(self._constants.TIMER_GANTT_INIT, gantt_mgr.init_data)
        QTimer.singleShot(self._constants.TIMER_INIT_DELAY, self._update_device_positions)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self._init_done or self._destroyed:
            return
        if self._panel_mgr and self._panel_mgr.any_visible():
            self._panel_mgr._show_click_catcher()
            self._schedule_position_update()
        if self._right_mgr:
            self._right_mgr.update_positions(self.ui.title_frame.height(), self.ui.stackedWidget.geometry())
        self._device_timer.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._destroyed = True
        self._position_timer.stop()
        self._device_timer.stop()
        for mgr in (
            self._anim_mgr,
            self._panel_mgr,
            self._right_mgr,
            self._shortcut_mgr,
        ):
            if mgr and hasattr(mgr, "cleanup"):
                mgr.cleanup()
        if self._injected_managers["legend"] and hasattr(self._injected_managers["legend"], "dispose"):
            self._injected_managers["legend"].dispose()
        if self._anim_mgr:
            self._anim_mgr.stop_all()
        if self._icons:
            self._icons.clear_cache()
        self.close_requested.emit()
        super().closeEvent(event)

    def _apply_theme(self, mode: str) -> None:
        """Apply theme mode with batched updates."""
        if self._destroyed:
            return
        mode = "light" if mode == "light" else "dark"
        self._state = self._state.with_theme(mode)
        self._icons.set_mode(mode)
        self._theme_applied = True
        if self._settings and hasattr(self._settings, "theme"):
            self._settings.theme = mode
        self.setUpdatesEnabled(False)
        try:
            if app := QApplication.instance():
                app.setStyleSheet(self._theme.render(mode))
            icon_size = self._constants.ICON_SIZE
            for widget in (
                self.ui.listWidget,
                self.ui.listWidget_settings,
                self.ui.pushButton,
            ):
                widget.setIconSize(icon_size)
            if self._menu_mgr:
                self._menu_mgr.refresh_icons()
            if self._panel_mgr:
                self._panel_mgr.settings_panel.update_icons()
                self._panel_mgr.hide_all()
            if self._right_mgr:
                self._right_mgr.update_icons()
            if self._device_mgr:
                self._device_mgr.set_theme(mode)
                self._device_mgr.update_all_positions()
            icon_path = Icons.CLOSE if self.ui.pushButton.isChecked() else Icons.OPEN
            self.ui.pushButton.setIcon(self._icons.icon(icon_path, self._constants.ICON_SIZE))
            if self._menu_mgr:
                self._menu_mgr.clear_selection()
            if mode == "dark":
                self.setWindowIcon(QIcon(Icons.LOGO))
                if app := QApplication.instance():
                    app.setWindowIcon(QIcon(Icons.LOGO))
            else:
                self.setWindowIcon(QIcon(Icons.LOGO))
                if app := QApplication.instance():
                    app.setWindowIcon(QIcon(Icons.LOGO))
        finally:
            self.setUpdatesEnabled(True)
        self._device_timer.start()
        self.theme_changed.emit(mode)

    def _toggle_theme(self) -> None:
        new_mode = "dark" if self._state.theme_mode == "light" else "light"
        self._apply_theme(new_mode)

    def _set_left_menu(self, expanded: bool, *, animate: bool) -> None:
        if self._destroyed:
            return
        icon_path = Icons.CLOSE if expanded else Icons.OPEN
        self.ui.pushButton.setIcon(self._icons.icon(icon_path, self._constants.ICON_SIZE))
        self.ui.title_icon.setVisible(expanded)
        self.ui.title_label.setVisible(expanded)
        if self._menu_mgr:
            self._menu_mgr.set_collapsed(not expanded)
        frame = self.ui.left_slide_menu_frame
        frame.setProperty("collapsed", not expanded)
        frame.style().unpolish(frame)
        frame.style().polish(frame)
        target = self._constants.MENU_WIDTH_EXPANDED if expanded else self._constants.MENU_WIDTH_COLLAPSED
        if animate and self._anim_mgr:
            self._anim_mgr.animate(self._anim_target.LEFT_MENU, frame, target)
        elif self._anim_mgr:
            self._anim_mgr.set_immediate(frame, target)
            if self._init_done and self._panel_mgr and self._panel_mgr.any_visible():
                self._schedule_position_update()
        self._state = self._state.with_menu_expanded(expanded)

    def _toggle_left_menu(self) -> None:
        self.ui.pushButton.setChecked(not self.ui.pushButton.isChecked())

    def _set_right_menu(self, expanded: bool, *, animate: bool) -> None:
        if self._destroyed or not self._right_mgr:
            return
        (current, target) = self._right_mgr.set_expanded(expanded, animate=False)
        if expanded:
            target = self._get_right_panel_target_width(target)
            self._load_right_panel_data()
        if animate and current != target and self._anim_mgr:
            self._anim_mgr.animate(self._anim_target.RIGHT_PANEL, self._right_mgr.frame, target)
        elif self._anim_mgr:
            self._anim_mgr.set_immediate(self._right_mgr.frame, target)

    def _get_right_panel_target_width(self, default: int) -> int:
        saved = self._settings.get("right_panel_width", default) if self._settings and hasattr(self._settings, "get") else default
        return max(
            self._constants.RIGHT_PANEL_WIDTH_MIN,
            min(saved, self._constants.RIGHT_PANEL_WIDTH_MAX),
        )

    def _toggle_right_menu(self) -> None:
        if self._right_mgr:
            self._set_right_menu(not self._right_mgr.is_expanded, animate=True)

    def _load_right_panel_data(self) -> None:
        if self._current_history_type in HistoryType.ALL and self._current_history_device:
            self._load_device_history_data()
        else:
            self._load_summary_for_current_page()

    def _load_summary_for_current_page(self, days: int = 7) -> None:
        if not (widget := self._get_right_menu_widget()):
            return
        self._current_history_device = None
        self._current_history_type = HistoryType.SUMMARY
        if hasattr(widget, "set_page"):
            widget.set_page(self._state.current_page)
        else:
            logger.warning(f"[MainView] Right panel widget does not support set_page. Type: {type(widget)}")
        widget.start_loading("Loading summary...")
        devices = getattr(widget, "_current_devices", [])
        if not devices:
            widget.clear_rows()
            widget.stop_loading()
            return
        self._request_summary_data(devices, days)

    def _load_device_history_data(self) -> None:
        if not self._current_history_device or not self._current_history_type:
            return
        if widget := self._get_right_menu_widget():
            if hasattr(widget, "set_title"):
                title = HistoryType.get_display_name(self._current_history_type)
                widget.set_title(f"{title}: {self._current_history_device}")
            if hasattr(widget, "start_loading"):
                widget.start_loading("Loading history...")
        self._request_device_history(self._current_history_device, self._current_history_type, 7)

    def _get_right_menu_widget(self) -> Optional[Any]:
        return self._right_mgr.menu_widget if self._right_mgr else None

    def _on_right_menu_data_request(self, devices: List[str], days: int) -> None:
        if widget := self._get_right_menu_widget():
            widget.start_loading("Refreshing...")
        if self._current_history_type in HistoryType.ALL and self._current_history_device:
            self._request_device_history(self._current_history_device, self._current_history_type, days)
        else:
            self._request_summary_data(devices, days)

    def _request_summary_data(self, devices: List[str], days: int) -> None:
        if self._db_bridge and hasattr(self._db_bridge, "request_summary_data"):
            try:
                self._db_bridge.request_summary_data(devices, days)
            except Exception as e:
                logger.error(f"Summary request failed: {e}")
                self._stop_right_menu_loading()

    def _request_device_history(self, device: str, dtype: str, days: int) -> None:
        if self._db_bridge and hasattr(self._db_bridge, "request_device_history"):
            try:
                self._db_bridge.request_device_history(device, dtype, days)
            except Exception as e:
                logger.error(f"History request failed: {e}")
                self._stop_right_menu_loading()

    def _request_gantt_data(self, device_code: str, frame_name: str) -> None:
        if self._db_bridge and hasattr(self._db_bridge, "request_gantt_data"):
            try:
                self._db_bridge.request_gantt_data(device_code, frame_name)
            except Exception as e:
                logger.error(f"Gantt request failed: {e}")

    def _stop_right_menu_loading(self) -> None:
        if widget := self._get_right_menu_widget():
            widget.stop_loading()

    def _on_gantt_data_ready(self, device_code: str, segments: List, start: Any, end: Any) -> None:
        gantt_mgr = self._injected_managers["gantt"]
        if not gantt_mgr:
            logger.debug(f"Gantt data for {device_code} received but GanttManager is None.")
            return
        frame = self._get_gantt_frame_for_device(device_code)
        if not frame:
            logger.warning(f"No Gantt frame found for device {device_code}. Data ignored.")
            return
        gantt_mgr.set_data(frame, device_code, segments, start, end)

    def _get_gantt_frame_for_device(self, device_code: str) -> Optional[str]:
        gantt_mgr = self._injected_managers["gantt"]
        if not gantt_mgr:
            return None
        if hasattr(gantt_mgr, "get_frame_for_device"):
            return gantt_mgr.get_frame_for_device(device_code)
        if current := self.ui.stackedWidget.currentWidget():
            page = current.objectName()
            return f"{page}_gantt"
        return None

    def _on_table_data_ready(self, data: Dict[str, Any]) -> None:
        if not (widget := self._get_right_menu_widget()):
            logger.debug("Table data received but right panel widget is not available.")
            return
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        device = data.get("device_code", "")
        dtype = data.get("data_type", "status")
        widget.set_title(f"{HistoryType.get_display_name(dtype)}: {device}")
        widget.set_headers(headers)
        if rows and isinstance(rows[0], dict):
            widget.load_dict_rows(rows)
        elif rows and headers:
            widget.load_dict_rows([dict(zip(headers, r)) for r in rows])
        else:
            widget.clear_rows()
        widget.set_status_column(data.get("status_col", -1) if dtype == "status" else -1)
        widget.stop_loading()

    def _on_summary_data_ready(self, records: List) -> None:
        if widget := self._get_right_menu_widget():
            widget.load_from_history(records)
            widget.stop_loading()
        else:
            logger.debug("Summary data received but right panel widget is not available.")

    def _on_click_outside(self, pos: QPoint) -> None:
        if self._destroyed or not self._panel_mgr:
            return
        global_pos = self._panel_mgr.click_catcher.mapTo(self.ui.centralwidget, pos)
        if self._get_settings_item_rect().contains(global_pos):
            self._panel_mgr.hide_all()
            self._panel_mgr.toggle_settings()
            return
        self._panel_mgr.handle_click_outside(global_pos)
        if self.ui.pushButton.isChecked() and self.ui.stackedWidget.geometry().contains(global_pos):
            self.ui.pushButton.setChecked(False)

    def _on_theme_button_clicked(self) -> None:
        if not self._panel_mgr:
            return
        if self._panel_mgr.theme_panel.isVisible():
            self._panel_mgr.theme_panel.hide()
        else:
            self._panel_mgr.show_theme_panel()

    def _on_menu_item_clicked(self, item: QListWidgetItem) -> None:
        if self._destroyed:
            return
        if self._panel_mgr:
            self._panel_mgr.hide_all()
        row = self.ui.listWidget.row(item)
        if self._menu_mgr and (page := self._menu_mgr.get_page_for_item(row)):
            self._navigate_to_page(page)
        if self._menu_mgr:
            self._menu_mgr.clear_selection()
        self.menu_item_clicked.emit(row)

    def _on_settings_clicked(self, item: QListWidgetItem) -> None:
        if self._destroyed:
            return
        if self._menu_mgr:
            self._menu_mgr.clear_selection()
        if self._panel_mgr:
            self._panel_mgr.toggle_settings()

    def _on_page_changed(self) -> None:
        if self._destroyed:
            return
        if current := self.ui.stackedWidget.currentWidget():
            page = current.objectName()
            self._state = self._state.with_page(page)
            if self._right_mgr:
                self._right_mgr.set_page(page)
            if self._current_history_type in HistoryType.ALL:
                self._current_history_device = None
                self._current_history_type = HistoryType.SUMMARY
            if self._right_mgr and self._right_mgr.is_expanded:
                self._load_summary_for_current_page()
        self._device_timer.start()
        self.page_requested.emit(self._state.current_page)

    def _on_device_clicked(self, device_id: str, device_name: str) -> None:
        self.device_clicked.emit(device_id, device_name)
        gantt_mgr = self._injected_managers["gantt"]
        if gantt_mgr and (current := self.ui.stackedWidget.currentWidget()):
            frame = self._get_gantt_frame_for_device(device_id)
            if frame:
                self._request_gantt_data(device_id, frame)

    def _on_context_menu_requested(self, device_id: str, device_name: str, pos: Any) -> None:
        if self._context_menu_provider:
            self._context_menu_provider(device_id, device_name, pos)
        else:
            logger.debug(f"No context menu provider for {device_id}")

    def _navigate_to_page(self, page_name: str) -> None:
        for i in range(self.ui.stackedWidget.count()):
            if self.ui.stackedWidget.widget(i).objectName() == page_name:
                self.ui.stackedWidget.setCurrentIndex(i)
                break

    def _next_page(self) -> None:
        stack = self.ui.stackedWidget
        if stack.count() > 0:
            stack.setCurrentIndex((stack.currentIndex() + 1) % stack.count())
            if self._menu_mgr:
                self._menu_mgr.clear_selection()

    def _prev_page(self) -> None:
        stack = self.ui.stackedWidget
        if stack.count() > 0:
            stack.setCurrentIndex((stack.currentIndex() - 1) % stack.count())
            if self._menu_mgr:
                self._menu_mgr.clear_selection()

    def _go_to_page(self, index: int) -> None:
        if 0 <= index < self.ui.stackedWidget.count():
            self.ui.stackedWidget.setCurrentIndex(index)
            if self._panel_mgr:
                self._panel_mgr.hide_all()
            if self._menu_mgr:
                self._menu_mgr.clear_selection()

    def _on_escape(self) -> None:
        if self._panel_mgr and self._panel_mgr.any_visible():
            self._panel_mgr.hide_all()
        elif self._right_mgr and self._right_mgr.is_expanded:
            self._set_right_menu(False, animate=True)
        elif self.isFullScreen():
            self._toggle_fullscreen()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    def _toggle_edit_mode(self) -> None:
        if self._device_mgr:
            self._device_mgr.toggle_edit_mode()

    def _show_info(self) -> None:
        if self._panel_mgr:
            self._panel_mgr.hide_all()
        QMessageBox.information(self, "Information", Shortcuts.INFO_TEXT)

    def _get_settings_item_rect(self) -> QRect:
        lw = self.ui.listWidget_settings
        if lw.count() > 0:
            rect = lw.visualItemRect(lw.item(0))
            top_left = lw.viewport().mapTo(self.ui.centralwidget, rect.topLeft())
            return QRect(top_left, rect.size())
        return QRect()

    def _schedule_position_update(self) -> None:
        if not self._position_timer.isActive():
            self._position_timer.start()

    def _do_position_update(self) -> None:
        if not self._destroyed and self._panel_mgr and self._panel_mgr.any_visible():
            self._panel_mgr.update_positions()

    @property
    def state(self) -> ViewState:
        return self._state

    def get_current_theme(self) -> str:
        return self._state.theme_mode

    def apply_theme(self, mode: str, stylesheet: str) -> None:
        """Apply theme from external controller."""
        if self._destroyed:
            return
        self._apply_theme(mode)

    def navigate_to_page(self, page_name: str) -> bool:
        self._navigate_to_page(page_name)
        return True

    def set_tooltip_provider(self, provider: TooltipProvider) -> None:
        self._tooltip_provider = provider
        if self._device_mgr:
            self._device_mgr.set_tooltip_callback(provider)

    def set_context_menu_provider(self, provider: ContextMenuProvider) -> None:
        self._context_menu_provider = provider
        if self._device_mgr:
            self._device_mgr.set_context_menu_callback(provider)

    def update_device_statuses(self, statuses: List[Dict[str, Any]]) -> None:
        if not self._destroyed and self._device_mgr:
            status_dict = {s.get("equip_code", s.get("id")): s for s in statuses}
            self._device_mgr.update_all_status(status_dict)

    def update_device_inputs(self, inputs: List[Dict[str, Any]]) -> None:
        pass

    def get_page_names(self) -> List[str]:
        return [self.ui.stackedWidget.widget(i).objectName() for i in range(self.ui.stackedWidget.count())]

    def get_current_page(self) -> str:
        if current := self.ui.stackedWidget.currentWidget():
            return current.objectName()
        return ""

    def is_left_menu_expanded(self) -> bool:
        return self._state.left_menu_expanded

    def set_left_menu_expanded(self, expanded: bool) -> None:
        self._set_left_menu(expanded, animate=True)

    def is_right_panel_visible(self) -> bool:
        return self._right_mgr.is_expanded if self._right_mgr else False

    def set_right_panel_visible(self, visible: bool) -> None:
        self._set_right_menu(visible, animate=True)

    def register_device_widget(self, device_code: str, widget: Any) -> None:
        self._device_widgets[device_code] = widget

    def update_all_device_statuses(self, statuses: Dict[str, Any]) -> None:
        if self._destroyed:
            return
        if self._device_mgr:
            self._device_mgr.update_all_status(statuses)
        for code, status in statuses.items():
            if (widget := self._device_widgets.get(code)) and hasattr(widget, "update_status"):
                if hasattr(status, "status_code"):
                    widget.update_status(status.status_code, status.status_color)
                elif isinstance(status, dict):
                    widget.update_status(
                        status.get("status_code", "0"),
                        status.get("status_color", "#808080"),
                    )

    def show_gantt_chart(self, frame_name: str, segments: list, chart_info: Any = None) -> None:
        gantt_mgr = self._injected_managers["gantt"]
        if not gantt_mgr:
            return
        try:
            gantt_mgr.set_data(frame_name, "", segments, None, None)
        except Exception as e:
            logger.error(f"show_gantt_chart failed: {e}", exc_info=True)


__all__ = ["MainView", "ViewState", "MenuItem"]
