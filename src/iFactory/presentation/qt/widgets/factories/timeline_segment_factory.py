# File: src\iFactory\presentation\qt\widgets\factories\timeline_segment_factory.py
"""
Gantt Chart Manager - UI Infrastructure.

Manages Gantt strip widgets across frames.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

try:
    from iFactory.presentation.managers.widgets.gantt.strip import GanttStrip
except ImportError:
    GanttStrip = None

from iFactory.domain.value_objects.time_range import TimeRange

logger = logging.getLogger(__name__)
_GanttStrip = None
_HAS_GANTT = False
try:
    # Thử import từ đường dẫn cũ (có thể sẽ fail)
    from iFactory.ui.widgets.gantt import GanttStrip

    _GanttStrip = GanttStrip
    _HAS_GANTT = True
except ImportError:
    # FIX: Đổi logger.warning thành logger.debug/info để không còn warning log
    logger.info("[GanttStrip] GanttStrip not available - Feature disabled")
__all__ = ["GanttManager", "GanttConfig", "FrameMetadata", "create_gantt_manager"]


@dataclass(slots=True)
class GanttConfig:
    """Gantt chart configuration."""

    show_summary: bool = False
    show_axis: bool = True
    show_now_line: bool = True
    show_segment_labels: bool = True
    min_height: int = 38
    default_range_hours: int = 24
    max_segments: int = 1000
    cache_results: bool = True
    max_retries: int = 3


@dataclass
class FrameMetadata:
    """Metadata for a registered frame."""

    frame: QFrame
    widget: Any
    device_code: str = ""
    last_loaded: Optional[datetime] = None
    segment_count: int = 0
    loading: bool = False
    error_count: int = 0


class TimelineSegmentFactory(QObject):
    """Manages Gantt chart widgets and data loading."""

    segment_clicked = Signal(str, object)
    data_loaded = Signal(str, int)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        db: Any = None,
        config: Optional[GanttConfig] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._db = db
        self._config = config or GanttConfig()
        self._frames: Dict[str, FrameMetadata] = {}
        self._theme = "light"
        self._theme_colors: Optional[Dict[str, str]] = None
        self._reader: Any = None
        self._initialized = False
        self._lock = asyncio.Lock()
        self._update_time_range()

    def _update_time_range(self) -> None:
        """Update default time range."""
        now = datetime.now()
        self._default_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self._default_end = self._default_start + timedelta(days=1)

    def _ensure_widget_valid(self, name: str) -> bool:
        """
        Check if widget for the given frame is still valid (C++ object alive).

        If invalid, unregisters the frame and returns False.

        Args:
            name: Frame name

        Returns:
            True if widget is valid, False otherwise
        """
        if name not in self._frames:
            return False
        metadata = self._frames[name]
        if not metadata.widget:
            self._unregister(name)
            return False
        try:
            _ = metadata.widget.isVisible()
            return True
        except RuntimeError:
            logger.debug(f"[GanttManager] Widget for '{name}' was deleted (RuntimeError)")
            self._unregister(name)
            return False

    async def initialize(self) -> None:
        """Initialize manager."""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized or not self._db:
                return
            try:
                self._reader = None
                logger.info("[GanttManager] Gantt reader initialization skipped (refactoring needed)")
            except ImportError:
                logger.warning("[GanttManager] No reader available")
            self._initialized = True

    async def dispose(self) -> None:
        """Dispose manager."""
        for name in list(self._frames.keys()):
            self._unregister(name)
        self._frames.clear()
        if self._reader and hasattr(self._reader, "clear_cache"):
            self._reader.clear_cache()
        self._reader = None
        self._initialized = False
        logger.info("[GanttManager] Disposed")

    def register_frame(
        self,
        name: str,
        frame: QFrame,
        show_summary: Optional[bool] = None,
        min_height: Optional[int] = None,
    ) -> Any:
        """Register a frame for Gantt display."""
        if not _HAS_GANTT or _GanttStrip is None or (not frame):
            logger.info(f"[GanttManager] Cannot register frame '{name}': GanttStrip not available")
            return None
        if name in self._frames:
            if not self._ensure_widget_valid(name):
                pass
            else:
                metadata = self._frames[name]
                if not metadata.widget.isHidden():
                    return metadata.widget
        self._unregister(name)
        try:
            old_layout = frame.layout()
            if old_layout:
                QWidget().setLayout(old_layout)
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            gantt = _GanttStrip(frame)
            gantt.setMinimumHeight(min_height or self._config.min_height)
            gantt.set_theme(self._theme)
            gantt.set_axis_visible(self._config.show_axis)
            gantt.set_now_line_visible(self._config.show_now_line)
            gantt.set_segment_labels_visible(self._config.show_segment_labels)
            gantt.set_show_summary(show_summary if show_summary is not None else self._config.show_summary)
            if self._theme_colors and hasattr(gantt, "set_colors"):
                gantt.set_colors(self._theme_colors)
            gantt.segmentClicked.connect(lambda seg: self.segment_clicked.emit(name, seg))
            layout.addWidget(gantt, 1)
            self._frames[name] = FrameMetadata(frame=frame, widget=gantt)
            logger.debug(f"Registered Gantt frame: {name}")
            return gantt
        except Exception as e:
            logger.error(f"Failed to register Gantt frame '{name}': {e}")
            self.error_occurred.emit(name, str(e))
            return None

    def _unregister(self, name: str) -> None:
        """Unregister a frame."""
        if name in self._frames:
            metadata = self._frames[name]
            if metadata.widget:
                try:
                    metadata.widget.deleteLater()
                except RuntimeError:
                    pass
            del self._frames[name]

    def unregister_frame(self, name: str) -> None:
        """Unregister a frame."""
        self._unregister(name)

    def set_device_data(
        self,
        frame_name: str,
        device_code: str,
        segments: List[Tuple[datetime, datetime, str]],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> bool:
        """Set device data for a frame."""
        if not self._ensure_widget_valid(frame_name):
            logger.debug(f"[GanttManager] Frame not registered or widget dead: {frame_name}")
            return False
        metadata = self._frames[frame_name]
        normalized = self._normalize_segments(segments)
        if len(normalized) > self._config.max_segments:
            logger.warning(f"Truncating {len(normalized)} segments to {self._config.max_segments}")
            normalized = normalized[: self._config.max_segments]
        try:
            metadata.widget.set_data(normalized, start or self._default_start, end or self._default_end)
            metadata.widget.set_title(device_code)
        except RuntimeError as e:
            logger.warning(f"[GanttManager] Widget access failed: {e}")
            self._unregister(frame_name)
            return False
        metadata.device_code = device_code
        metadata.segment_count = len(normalized)
        metadata.last_loaded = datetime.now()
        self.data_loaded.emit(frame_name, len(normalized))
        return True

    async def load_device(
        self,
        frame_name: str,
        device_code: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        force_reload: bool = False,
    ) -> bool:
        """Load device data for a frame."""
        if frame_name not in self._frames:
            logger.warning(f"Frame not registered: {frame_name}")
            return False
        if not self._ensure_widget_valid(frame_name):
            return False
        metadata = self._frames[frame_name]
        if metadata.loading:
            logger.debug(f"Already loading: {frame_name}")
            return False
        if not self._initialized:
            await self.initialize()
        if not self._reader:
            self.error_occurred.emit(frame_name, "No data reader available")
            return False
        metadata.loading = True
        start = start or self._default_start
        end = end or self._self._default_end
        try:
            if hasattr(self._reader, "fetch_segments"):
                segments = await self._reader.fetch_segments(device_code, start, end, not force_reload)
            else:
                segments = await self._reader.fetch_for_gantt(device_code, start, end)
            if not self._ensure_widget_valid(frame_name):
                return False
            metadata = self._frames[frame_name]
            if segments:
                normalized = self._normalize_segments(segments)
                if len(normalized) > self._config.max_segments:
                    normalized = normalized[: self._config.max_segments]
                metadata.widget.set_data(normalized, start, end)
                metadata.widget.set_title(device_code)
                metadata.device_code = device_code
                metadata.segment_count = len(normalized)
                metadata.error_count = 0
                metadata.last_loaded = datetime.now()
                self.data_loaded.emit(frame_name, len(normalized))
            else:
                metadata.widget.clear_data()
                metadata.widget.set_placeholder(f"{device_code}: No data")
                metadata.widget.set_title(device_code)
                metadata.device_code = device_code
                metadata.segment_count = 0
            return True
        except RuntimeError as e:
            logger.warning(f"[GanttManager] Widget for {frame_name} died during load: {e}")
            self._unregister(frame_name)
            return False
        except Exception as e:
            logger.error(f"Failed to load {device_code} for {frame_name}: {e}")
            metadata.error_count += 1
            self.error_occurred.emit(frame_name, str(e))
            if metadata.error_count < self._config.max_retries:
                await asyncio.sleep(1)
                return await self.load_device(frame_name, device_code, start, end)
            return False
        finally:
            if frame_name in self._frames:
                self._frames[frame_name].loading = False

    def _normalize_segments(self, segments: List[Tuple[datetime, datetime, str]]) -> List[Tuple[datetime, datetime, str]]:
        """Normalize status codes in segments."""
        try:
            from iFactory.domain.value_objects.status import Status

            normalized = []
            for start, end, status_code in segments:
                try:
                    status = Status.from_code(str(status_code))
                    normalized.append((start, end, status.name))
                except Exception:
                    normalized.append((start, end, str(status_code)))
            return normalized
        except ImportError:
            return segments

    def set_theme(self, theme: str) -> None:
        """Set theme for all widgets."""
        self._theme = "dark" if theme == "dark" else "light"
        for name, metadata in list(self._frames.items()):
            if self._ensure_widget_valid(name):
                try:
                    metadata.widget.set_theme(self._theme)
                except RuntimeError:
                    self._unregister(name)

    def set_theme_colors(self, colors: Optional[Dict[str, str]] = None) -> None:
        """
        Set custom theme colors for Gantt widgets.

        Args:
            colors: Dictionary with theme colors, e.g.:
                {
                    "running": "#4CAF50",
                    "stop": "#F44336",
                    ...
                }
        """
        self._theme_colors = colors
        try:
            from iFactory.ui.widgets.gantt import GanttThemeProvider

            if colors:
                GanttThemeProvider.set_colors(colors)
        except (ImportError, AttributeError):
            pass
        for name, metadata in list(self._frames.items()):
            if self._ensure_widget_valid(name):
                try:
                    if hasattr(metadata.widget, "set_colors") and colors:
                        metadata.widget.set_colors(colors)
                    metadata.widget.set_theme(self._theme)
                except RuntimeError:
                    self._unregister(name)
        count = len(colors) if colors else 0
        logger.debug(f"Theme colors updated: {count} colors")

    def get_widget(self, name: str) -> Any:
        """Get widget for a frame."""
        if not self._ensure_widget_valid(name):
            return None
        metadata = self._frames.get(name)
        return metadata.widget if metadata else None

    def get_current_device(self, name: str) -> Optional[str]:
        """Get current device code for a frame."""
        if not self._ensure_widget_valid(name):
            return None
        metadata = self._frames.get(name)
        return metadata.device_code if metadata else None

    def get_all_frames(self) -> List[str]:
        """Get all registered frame names."""
        for name in list(self._frames.keys()):
            self._ensure_widget_valid(name)
        return list(self._frames.keys())

    def clear_frame(self, name: str) -> None:
        """Clear data for a frame."""
        if not self._ensure_widget_valid(name):
            return
        metadata = self._frames.get(name)
        if metadata and metadata.widget:
            try:
                metadata.widget.clear_data()
                metadata.device_code = ""
                metadata.segment_count = 0
            except RuntimeError:
                self._unregister(name)

    def clear_all_frames(self) -> None:
        """Clear all frames."""
        for name in list(self._frames.keys()):
            self.clear_frame(name)

    def clear_cache(self) -> None:
        """Clear data cache."""
        if self._reader and hasattr(self._reader, "clear_cache"):
            self._reader.clear_cache()

    def set_time_range(self, hours: int) -> None:
        """Set default time range in hours."""
        self._config.default_range_hours = hours
        self._update_time_range()

    async def reload_all(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> Dict[str, bool]:
        """Reload all frames."""
        results = {}
        valid_names = self.get_all_frames()
        for name in valid_names:
            metadata = self._frames.get(name)
            if metadata and metadata.device_code:
                result = await self.load_device(name, metadata.device_code, start, end)
                results[name] = result
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "frames": len(self._frames),
            "devices": len([m for m in self._frames.values() if m.device_code]),
            "segments": sum((m.segment_count for m in self._frames.values())),
            "loading": sum((1 for m in self._frames.values() if m.loading)),
            "theme": self._theme,
            "initialized": self._initialized,
        }


def create_gantt_manager(
    db: Any = None,
    show_summary: bool = False,
    default_hours: int = 24,
    parent: Optional[QObject] = None,
) -> TimelineSegmentFactory:
    """
    Factory function to create GanttManager.

    Args:
        db: Database orchestrator
        show_summary: Show summary statistics
        default_hours: Default time range in hours
        parent: Qt parent

    Returns:
        Configured GanttManager
    """
    config = GanttConfig(show_summary=show_summary, default_range_hours=default_hours)
    return TimelineSegmentFactory(db=db, config=config, parent=parent)
