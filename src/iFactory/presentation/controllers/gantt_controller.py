# File: presentation/controllers/gantt_controller.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from ..adapters.async_executor import AsyncExecutor
from ..state.actions import load_gantt

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..state.store import Store

logger = logging.getLogger(__name__)


class GanttController(QObject):
    """Controller for Gantt chart operations."""

    device_gantt_ready = Signal(object)  # GanttChartViewModel
    loading_started = Signal()
    loading_finished = Signal()

    def __init__(
        self,
        device_service,
        presenter: "GanttPresenter",
        store: "Store",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store

        self._executor = AsyncExecutor(max_workers=2, parent=self)
        self._cache: Dict[str, Any] = {}

    def load_timeline(self, days: int = 1) -> None:
        """Load timeline data for all devices."""
        logger.info(f"Loading timeline for {days} day(s)...")
        self._executor.execute(
            self._fetch_timeline(days),
            on_success=self._on_fetch_success,
            on_error=self._on_fetch_error,
        )

    def load_device_gantt(self, device_code: str, device_name: str = "") -> None:
        """Load Gantt chart for a specific device (24h)."""
        self.loading_started.emit()

        self._executor.execute(
            self._fetch_device_gantt(device_code, device_name or device_code),
            on_success=self._on_device_gantt_success,
            on_error=self._on_device_gantt_error,
        )

    async def _fetch_timeline(self, days: int) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch timeline data for multiple devices."""
        if not self._service:
            logger.warning("No device service available")
            return {}

        state = self._store.get_state()
        devices = state.get("devices", {})

        if not devices:
            logger.warning("No devices in state")
            return {}

        target_codes = list(devices.keys())[:20]
        logger.info(f"Fetching gantt for {len(target_codes)} devices")

        result: Dict[str, List[Dict[str, Any]]] = {}

        for code in target_codes:
            try:
                data = await self._service.generate_gantt_segments(code, days=days)
                segments = data.get("segments", [])

                if segments:
                    # Convert segments to serializable format with datetime objects
                    processed_segments = []
                    for seg in segments:
                        processed_seg = self._process_segment(seg)
                        if processed_seg:
                            processed_segments.append(processed_seg)

                    if processed_segments:
                        result[code] = processed_segments
                        logger.debug(f"Loaded {len(processed_segments)} segments for {code}")

            except Exception as e:
                logger.debug(f"Gantt fetch failed for {code}: {e}")

        logger.info(f"Gantt data fetched for {len(result)} devices")
        return result

    def _process_segment(self, seg: Any) -> Optional[Dict[str, Any]]:
        """Process a segment into a consistent dict format."""
        try:
            if isinstance(seg, dict):
                start = seg.get("start_time") or seg.get("start")
                end = seg.get("end_time") or seg.get("end")
                status = seg.get("status_code") or seg.get("status", 0)
            else:
                start = getattr(seg, "start_time", None) or getattr(seg, "start", None)
                end = getattr(seg, "end_time", None) or getattr(seg, "end", None)
                status = getattr(seg, "status_code", None) or getattr(seg, "status", 0)

            # Parse datetime if string
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))

            if not isinstance(start, datetime) or not isinstance(end, datetime):
                return None

            # Parse status code
            if isinstance(status, str):
                status_map = {
                    "running": 1,
                    "run": 1,
                    "shutdown": 2,
                    "stopped": 3,
                    "stop": 3,
                    "maintenance": 4,
                    "alarm": 5,
                }
                status = status_map.get(status.lower(), 0)

            return {
                "start_time": start,
                "end_time": end,
                "status_code": int(status) if status else 0,
            }
        except Exception as e:
            logger.debug(f"Failed to process segment: {e}")
            return None

    async def _fetch_device_gantt(
        self,
        device_code: str,
        device_name: str,
    ) -> Optional[object]:
        """Fetch detailed Gantt data for a single device."""
        if not self._service:
            return None

        try:
            end = datetime.now()
            start = end - timedelta(hours=24)

            data = await self._service.generate_gantt_segments(device_code, days=1)
            segments = data.get("segments", [])

            return self._presenter.present_device_chart(
                device_code=device_code,
                device_name=device_name,
                segments_dto=segments,
                window_start=start,
                window_end=end,
            )
        except Exception as e:
            logger.error(f"Failed to fetch Gantt for {device_code}: {e}")
            return None

    def _on_fetch_success(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        if data:
            self._store.dispatch(load_gantt(data))
            logger.info(f"Gantt state updated with {len(data)} devices")
        else:
            logger.warning("Gantt fetch returned empty data")

    def _on_fetch_error(self, error: Exception) -> None:
        logger.error(f"Gantt fetch failed: {error}")

    def _on_device_gantt_success(self, view_model: Optional[object]) -> None:
        self.loading_finished.emit()

        if view_model:
            self.device_gantt_ready.emit(view_model)
            logger.debug(f"Device Gantt loaded: {getattr(view_model, 'device_code', 'unknown')}")

    def _on_device_gantt_error(self, error: Exception) -> None:
        self.loading_finished.emit()
        logger.error(f"Device Gantt fetch failed: {error}")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


__all__ = ["GanttController"]
