# File: src/iFactory/ui/main_window/device_manager.py
"""
Device Integration Manager - Bridges infrastructure and presentation.
Accepts pre-created infrastructure managers via dependency injection.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from collections import NamedTuple
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtWidgets import QMessageBox

from iFactory.ui.widgets.constants import (
    CONTEXT_MENU_STYLESHEET,
    GANTT_PAGE_MAPPING,
    DefaultGanttDevices,
    HistoryType,
)

if TYPE_CHECKING:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu, QWidget

    from iFactory.infrastructure.configuration.device_config_loader import (
        DeviceLayoutManager,
    )
    from iFactory.infrastructure.configuration.legend.manager import (
        LegendManager,
    )
    from iFactory.infrastructure.factories.timeline_segment_factory import (
        GanttManager,
    )
    from iFactory.ui.widgets.constants import WindowConstants
logger = logging.getLogger(__name__)

DeviceClickCallback = Callable[[str, str], None]
HistoryCallback = Callable[[str, str, str], None]
GanttRequestCallback = Callable[[str, str], None]


class NormalizedStatus(NamedTuple):
    """Normalized status representation."""

    code: str
    name: str
    display: str
    color_light: str
    color_dark: str

    def __new__(cls, code: str, name: str, display: str, color_light: str, color_dark: str):
        return super().__new__(cls, code, name, display, color_light, color_dark)


class StatusNormalizer:
    """
    Centralizes status code normalization across the system.

    Eliminates repeated extraction patterns throughout codebase.
    """

    STATUS_MAP: Dict[str, NormalizedStatus] = {
        "0": NormalizedStatus("0", "unknown", "Unknown", "#9E9E9E", "#757575"),
        "1": NormalizedStatus("1", "running", "Running", "#4CAF50", "#66BB6A"),
        "2": NormalizedStatus("2", "shutdown", "Shutdown", "#757575", "#616161"),
        "3": NormalizedStatus("3", "stop", "Stop", "#F44336", "#EF5350"),
        "4": NormalizedStatus("4", "maintenance", "Maintenance", "#2196F3", "#42A5F5"),
        "5": NormalizedStatus("5", "alarm", "Alarm", "#FF9800", "#FFA726"),
    }
    NAME_TO_CODE: Dict[str, str] = {
        "unknown": "0",
        "running": "1",
        "shutdown": "2",
        "stop": "3",
        "maintenance": "4",
        "alarm": "5",
    }

    @classmethod
    def normalize(cls, raw_value: Any) -> NormalizedStatus:
        """
        Normalize any status representation to canonical form.

        Accepts:
        - Code: "1", 1
        - Name: "running", "RUNNING"
        - Dict: {"status_code": "1"}, {"EQUIP_STATUS": 1}
        """
        code = cls._extract_code(raw_value)
        return cls.STATUS_MAP.get(code, cls.STATUS_MAP["0"])

    @classmethod
    def _extract_code(cls, raw_value: Any) -> str:
        """Extract status code from various formats."""
        if raw_value is None:
            return "0"
        if isinstance(raw_value, int):
            return str(raw_value)
        if isinstance(raw_value, str):
            if raw_value.lower() in cls.NAME_TO_CODE:
                return cls.NAME_TO_CODE[raw_value.lower()]
            return raw_value if raw_value in cls.STATUS_MAP else "0"
        if isinstance(raw_value, dict):
            for key in (
                "status_code",
                "status",
                "EQUIP_STATUS",
                "equip_status",
                "code",
            ):
                if (val := raw_value.get(key)) is not None:
                    if isinstance(val, dict):
                        continue
                    return cls._extract_code(val)
        if hasattr(raw_value, "status_code"):
            return cls._extract_code(raw_value.status_code)
        return "0"

    @classmethod
    def get_color(cls, code: str, theme: str = "light") -> str:
        """Get color for status code."""
        status = cls.STATUS_MAP.get(str(code), cls.STATUS_MAP["0"])
        return status.color_light if theme == "light" else status.color_dark


@dataclass(slots=True)
class DeviceDataCache:
    """Cache for device data (status, input, output)."""

    status: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    input: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    output: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def clear(self) -> None:
        """Clear all cached data."""
        self.status.clear()
        self.input.clear()
        self.output.clear()

    def get_device_data(self, device_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all cached data for a device."""
        return {
            "status": self.status.get(device_id, {}),
            "input": self.input.get(device_id, {}),
            "output": self.output.get(device_id, {}),
        }

    def get_status_code(self, device_id: str) -> Optional[str]:
        """Get status code for device."""
        if data := self.status.get(device_id):
            return data.get("equip_status") or data.get("EQUIP_STATUS")
        return None

    def get_status_info(self, device_id: str) -> Optional[Dict]:
        """Lấy thông tin status đầy đủ (name, color) từ cache nếu có."""
        return self.status.get(device_id)


class DeviceLayoutManager:
    """
    Manages device visualization components.
    Integrates DeviceLayoutManager, GanttManager, and LegendManager.
    """

    __slots__ = (
        "_theme",
        "_constants",
        "_parent",
        "_device_mgr",
        "_gantt_mgr",
        "_legend_mgr",
        "_cache",
        "_current_device_id",
        "_default_gantt_devices",
        "_device_click_cb",
        "_show_history_cb",
        "_request_gantt_cb",
        "_initialized_frames",
    )

    def __init__(
        self,
        theme_manager: Any,
        constants: Optional[WindowConstants] = None,
        parent: Optional[QWidget] = None,
        *,
        device_layout_manager: Optional[DeviceLayoutManager] = None,
        gantt_manager: Optional[GanttManager] = None,
        legend_manager: Optional[LegendManager] = None,
    ) -> None:
        self._theme = theme_manager
        self._parent = parent
        self._constants = constants or self._load_constants()
        self._device_mgr = device_layout_manager
        self._gantt_mgr = gantt_manager
        self._legend_mgr = legend_manager
        self._cache = DeviceDataCache()
        self._current_device_id: Optional[str] = None
        self._default_gantt_devices = DefaultGanttDevices().to_frame_mapping()
        self._initialized_frames: set[str] = set()
        self._device_click_cb: Optional[DeviceClickCallback] = None
        self._show_history_cb: Optional[HistoryCallback] = None
        self._request_gantt_cb: Optional[GanttRequestCallback] = None
        from iFactory.infrastructure.configuration.legend.status_registry import (
            get_status_registry,
        )

        self._status_registry = get_status_registry()

    @staticmethod
    def _load_constants() -> WindowConstants:
        from iFactory.ui.widgets.constants import WindowConstants

        return WindowConstants()

    def set_device_layout_manager(self, manager: DeviceLayoutManager) -> None:
        self._device_mgr = manager

    def set_gantt_manager(self, manager: GanttManager) -> None:
        self._gantt_mgr = manager

    def set_legend_manager(self, manager: LegendManager) -> None:
        self._legend_mgr = manager

    def initialize_device_manager(self, frames: Dict[str, Any], mode: str) -> None:
        """Initialize device manager with frames."""
        if not self._device_mgr:
            self._device_mgr = self._create_manager("devices", "DeviceLayoutManager")
            if not self._device_mgr:
                return
        self._device_mgr.set_theme(mode)
        self._device_mgr.set_click_callback(self._on_device_clicked)
        self._device_mgr.set_context_menu_callback(self._on_device_right_clicked)
        self._device_mgr.set_tooltip_callback(self._cache.get_device_data)
        self._register_frames(self._device_mgr, frames)
        logger.info("Device manager initialized: %s frames", len(frames))

    def initialize_gantt_manager(self, frames: Dict[str, Any], mode: str) -> None:
        """Initialize gantt manager with frames."""
        if not self._gantt_mgr:
            self._gantt_mgr = self._create_manager("gantt", "GanttManager", parent=self._parent)
            if not self._gantt_mgr:
                return
        self._gantt_mgr.set_theme(mode)
        self._register_gantt_frames(frames)
        if hasattr(self._gantt_mgr, "segment_clicked"):
            self._gantt_mgr.segment_clicked.connect(self._on_gantt_segment_clicked)
        logger.info(f"Gantt manager initialized: {len(frames)} frames")

    def initialize_legend_manager(self, frames: Dict[str, Any], mode: str) -> None:
        """Initialize legend manager with frames."""
        if not self._legend_mgr:
            self._legend_mgr = self._create_manager("legend", "LegendManager")
            if not self._legend_mgr:
                return
        self._legend_mgr.set_theme(mode)
        self._register_frames(self._legend_mgr, frames)
        logger.info(f"Legend manager initialized: {len(frames)} frames")

    def _create_manager(self, module: str, class_name: str, **kwargs: Any) -> Optional[Any]:
        """Create a manager instance dynamically."""
        try:
            mod = __import__(f"iFactory.infrastructure.{module}.manager", fromlist=[class_name])
            return getattr(mod, class_name)(**kwargs)
        except (ImportError, AttributeError) as e:
            logger.warning(f"{class_name} not available: {e}")
            return None

    def _register_frames(self, manager: Any, frames: Dict[str, Any]) -> None:
        """
        Register frames with a manager.

        FIX: Prevents duplicate UI registration by tracking initialized frames.
        """
        if not hasattr(manager, "register_frame"):
            return
        for name, frame in frames.items():
            if not frame:
                continue
            unique_id = f"{manager.__class__.__name__}_{name}"
            if unique_id in self._initialized_frames:
                continue
            self._initialized_frames.add(unique_id)
            manager.register_frame(name, frame)

    def _register_gantt_frames(self, frames: Dict[str, Any]) -> None:
        """Register frames with gantt manager."""
        if not self._gantt_mgr or not hasattr(self._gantt_mgr, "register_frame"):
            return
        for name, frame in frames.items():
            if frame:
                unique_id = f"Gantt_{name}"
                if unique_id not in self._initialized_frames:
                    self._initialized_frames.add(unique_id)
                    self._gantt_mgr.register_frame(name, frame, show_summary=False, min_height=38)

    def set_device_click_callback(self, callback: DeviceClickCallback) -> None:
        self._device_click_cb = callback

    def set_show_history_callback(self, callback: HistoryCallback) -> None:
        self._show_history_cb = callback

    def set_request_gantt_callback(self, callback: GanttRequestCallback) -> None:
        self._request_gantt_cb = callback

    def _on_device_clicked(self, device_id: str, device_name: str) -> None:
        """Handle device click - trigger Gantt update."""
        self._current_device_id = device_id
        frame_name = self._find_frame_for_device(device_id, fallback=False)
        if frame_name and self._request_gantt_cb:
            self._request_gantt_cb(device_id, frame_name)
        if self._device_click_cb:
            try:
                self._device_click_cb(device_id, device_name)
            except Exception as e:
                logger.error(f"Device click callback error: {e}")

    def _on_device_right_clicked(self, device_id: str, device_name: str, global_pos: QPoint) -> None:
        """Handle device right-click - show context menu."""
        self._current_device_id = device_id
        self._create_context_menu(device_id, device_name).exec(global_pos)

    def _create_context_menu(self, device_id: str, device_name: str) -> QMenu:
        """Create context menu for device."""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self._parent)
        menu.setStyleSheet(CONTEXT_MENU_STYLESHEET)
        for text, enabled in [(f"📱 {device_id}", False), (f"   {device_name}", False)]:
            action = QAction(text, menu)
            action.setEnabled(enabled)
            menu.addAction(action)
        cached_status = self._cache.get_status_info(device_id)
        if cached_status:
            status_code = cached_status.get("equip_status")
            status_info = self._status_registry.get_by_code(status_code)
            action = QAction(f"   Status: {status_info.label} ({status_code})", menu)
            action.setEnabled(False)
            menu.addAction(action)
        menu.addSeparator()
        for htype, icon, label in (
            (HistoryType.STATUS, "📋", "Status History"),
            (HistoryType.INPUT, "📥", "Input History"),
            (HistoryType.OUTPUT, "📤", "Output History"),
        ):
            action = menu.addAction(f"{icon}  {label}")
            action.triggered.connect(lambda _, d=device_id, n=device_name, t=htype: self._show_history(d, n, t))
        menu.addSeparator()
        gantt_action = menu.addAction("📊  Show Gantt Chart")
        gantt_action.triggered.connect(lambda: self._show_device_gantt(device_id))
        return menu

    def _show_history(self, device_id: str, device_name: str, history_type: str) -> None:
        """Show history for device."""
        if self._show_history_cb:
            try:
                self._show_history_cb(device_id, device_name, history_type)
            except Exception as e:
                logger.error(f"Show history error: {e}")
        else:
            QMessageBox.information(
                self._parent,
                f"{HistoryType.get_display_name(history_type)} History",
                f"Device: {device_id}\n(Callback not connected)",
            )

    def _show_device_gantt(self, device_id: str) -> None:
        """Show Gantt chart for specific device."""
        frame = self._find_frame_for_device(device_id, fallback=True)
        if frame:
            self.request_gantt_for_device(device_id, frame)

    def _find_frame_for_device(self, device_id: str, fallback: bool = False) -> Optional[str]:
        """
        Find appropriate frame for a device.
        """
        for frame, mapped in self._default_gantt_devices.items():
            if mapped == device_id:
                return frame
        if fallback:
            return next(iter(self._default_gantt_devices), None)
        return None

    def _on_gantt_segment_clicked(self, frame_name: str, segment: Optional[Tuple[datetime, datetime, str]]) -> None:
        """Handle Gantt segment click."""
        if not segment:
            return
        (start, end, status_code) = segment
        duration = int((end - start).total_seconds())
        status_info = self._status_registry.get_by_code(status_code)
        status_label = status_info.label
        device = (
            self._gantt_mgr.get_current_device(frame_name) if self._gantt_mgr and hasattr(self._gantt_mgr, "get_current_device") else "Unknown"
        ) or "Unknown"
        message = (
            f"Device: {device}\nStatus: {status_label}\n"
            f"Start: {start:%H:%M:%S}\nEnd: {end:%H:%M:%S}\n"
            f"Duration: {duration // 3600}h {duration % 3600 // 60}m"
        )
        QMessageBox.information(
            self._parent,
            "Segment Details",
            message,
        )

    def update_device_statuses(self, statuses: List[Dict[str, Any]]) -> None:
        """Update device status cache and display."""
        for status in statuses:
            code = self._extract_field(
                status,
                "EQUIP_CODE",
                "equip_code",
                "equipment_code",
                "device_code",
                "code",
            )
            if not code:
                continue
            raw_status = self._extract_field(status, "EQUIP_STATUS", "equip_status", "status_code", "status")
            status_info = self._status_registry.normalize(raw_status)
            normalized_code = status_info.db_code
            self._cache.status[code] = {
                "equip_code": code,
                "equip_status": normalized_code,
                "status_name": status_info.label,
                "status_color": status_info.get_color(self._theme.mode),
                "EQUIP_CODE": code,
                "EQUIP_STATUS": normalized_code,
                **status,
            }
        self._apply_status_updates()

    @staticmethod
    def _extract_field(data: Dict[str, Any], *keys: str) -> Optional[str]:
        """Extract first matching field from data."""
        for key in keys:
            if value := data.get(key):
                return str(value)
        return None

    def _apply_status_updates(self) -> None:
        """Apply cached status updates to device manager."""
        if not self._device_mgr:
            return
        status_map = {}
        for code, data in self._cache.status.items():
            status_map[code] = data.get("equip_status", "0")
        self._device_mgr.update_all_status(status_map)
        if hasattr(self._device_mgr, "set_color_map"):
            color_map = {code: data.get("status_color") for (code, data) in self._cache.status.items()}
            self._device_mgr.set_color_map(color_map)

    def update_device_inputs(self, inputs: List[Dict[str, Any]]) -> None:
        """Update device input cache."""
        for inp in inputs:
            code = self._extract_field(inp, "EQUIP_CODE", "equip_code", "equipment_code", "device_code")
            if code:
                self._cache.input[code] = inp

    def request_gantt_for_device(self, device_id: str, frame_name: str) -> None:
        """Request Gantt data for device."""
        if not device_id:
            return
        self._default_gantt_devices[frame_name] = device_id
        if self._request_gantt_cb:
            try:
                self._request_gantt_cb(device_id, frame_name)
            except Exception as e:
                logger.error(f"Request gantt error: {e}")

    def set_gantt_data(
        self,
        frame_name: str,
        device_id: str,
        segments: List,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> bool:
        """Set Gantt data for a frame."""
        if not self._gantt_mgr:
            return False
        try:
            res = self._gantt_mgr.set_device_data(frame_name, device_id, segments, start_time, end_time)
            if res and self._legend_mgr and hasattr(self._legend_mgr, "update_stats"):
                stats = self._calculate_legend_stats(segments, start_time, end_time)
                self._legend_mgr.update_stats(stats)
            return res
        except Exception as e:
            logger.error(f"Set gantt data error: {e}")
            return False

    def _calculate_legend_stats(self, segments: List, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Calculate total duration per status for the Legend."""
        stats = {}
        total_seconds = 0.0
        parsed_segments = []
        for seg in segments:
            if isinstance(seg, (tuple, list)) and len(seg) >= 3:
                parsed_segments.append({"start": seg[0], "end": seg[1], "status": str(seg[2])})
            elif hasattr(seg, "status_code"):
                parsed_segments.append({"start": seg.start, "end": seg.end, "status": str(seg.status_code)})
        for seg in parsed_segments:
            status = seg["status"]
            if not seg["start"] or not seg["end"]:
                continue
            duration = (seg["end"] - seg["start"]).total_seconds()
            if status not in stats:
                stats[status] = 0.0
            stats[status] += duration
            total_seconds += duration
        result = {}
        for status, duration in stats.items():
            info = self._status_registry.get_by_code(status)
            result[status] = {
                "duration_seconds": duration,
                "percentage": (duration / total_seconds * 100 if total_seconds > 0 else 0.0),
                "label": info.label,
                "color": info.get_color(self._theme.mode),
            }
        return result

    def init_gantt_data(self) -> None:
        """Initialize Gantt data for default devices."""
        for frame, device_id in self._default_gantt_devices.items():
            if device_id:
                self.request_gantt_for_device(device_id, frame)

    def get_gantt_frame_for_page(self, page_name: str) -> Optional[str]:
        """Get Gantt frame name for a page."""
        return GANTT_PAGE_MAPPING.get(page_name)

    def set_theme(self, mode: str) -> None:
        """Set theme for all managers."""
        self._theme.mode = mode
        for mgr in (self._device_mgr, self._legend_mgr, self._gantt_mgr):
            if mgr:
                mgr.set_theme(mode)
        self._apply_status_updates()

    def update_page_svg(self, mode: str, frames: Dict[str, Any]) -> None:
        """Update page SVG backgrounds."""
        if not self._device_mgr or not hasattr(self._theme, "get_page_svg"):
            return
        for name in frames:
            if svg := self._theme.get_page_svg(name, mode):
                self._device_mgr.load_svg_for_frame(name, svg)
        self._apply_status_updates()

    def toggle_edit_mode(self) -> bool:
        """Toggle edit mode for device manager."""
        return self._device_mgr.toggle_edit_mode() if self._device_mgr else False

    def update_device_positions(self) -> None:
        """Update device positions."""
        if self._device_mgr:
            self._device_mgr.refresh_all_widgets()

    @property
    def default_gantt_devices(self) -> Dict[str, str]:
        return self._default_gantt_devices.copy()

    @property
    def device_manager(self) -> Optional[DeviceLayoutManager]:
        return self._device_mgr

    @property
    def gantt_manager(self) -> Optional[GanttManager]:
        return self._gantt_mgr

    @property
    def legend_manager(self) -> Optional[LegendManager]:
        """Get the legend manager instance."""
        return self._legend_mgr

    @property
    def is_fully_initialized(self) -> bool:
        return all((self._device_mgr, self._gantt_mgr, self._legend_mgr))


__all__ = ["DeviceLayoutManager", "DeviceDataCache"]
