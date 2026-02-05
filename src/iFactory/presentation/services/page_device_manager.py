# src/iFactory/presentation/services/page_device_manager.py
"""
Page Device Manager - BACKWARD COMPATIBLE VERSION.

Supports both:
1. Legacy mode: PageDeviceManager(config_path=...)
2. Progressive mode: PageDeviceManager(progressive_loader=..., ...)

Usage (Legacy):
    manager = PageDeviceManager(config_path="path/to/config.json")
    manager.load_page("electrode_page", ["DEV01", "DEV02"])

Usage (Progressive):
    manager = PageDeviceManager(
        progressive_loader=loader,
        viewport_manager=viewport,
    )
    await manager.initial_load(page_id, device_ids)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING, Union

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from .progressive_loader import ProgressiveDeviceLoader, LoadingStage
    from .viewport_manager import DeviceViewportManager, ViewportChange
    from .device_status_service import DeviceStatusService

logger = logging.getLogger(__name__)


# ============================================================================
# Page State
# ============================================================================


@dataclass
class PageState:
    """State for a device page."""

    page_id: str
    all_device_ids: List[str]
    loaded_devices: Set[str] = field(default_factory=set)
    visible_devices: Set[str] = field(default_factory=set)
    prefetch_devices: Set[str] = field(default_factory=set)
    live_subscriptions: Set[str] = field(default_factory=set)

    # Timing
    load_started_at: Optional[datetime] = None
    initial_load_completed_at: Optional[datetime] = None

    @property
    def is_initial_load_complete(self) -> bool:
        return self.initial_load_completed_at is not None

    @property
    def initial_load_duration_ms(self) -> float:
        if not self.load_started_at or not self.initial_load_completed_at:
            return 0.0
        delta = self.initial_load_completed_at - self.load_started_at
        return delta.total_seconds() * 1000

    @property
    def load_progress(self) -> float:
        """Calculate load progress (0.0 to 1.0)."""
        if not self.all_device_ids:
            return 1.0
        return len(self.loaded_devices) / len(self.all_device_ids)


@dataclass
class PageMetrics:
    """Metrics for page operations."""

    total_page_loads: int = 0
    total_scrolls: int = 0
    total_device_clicks: int = 0
    avg_initial_load_ms: float = 0.0
    active_subscriptions: int = 0

    def record_page_load(self, duration_ms: float) -> None:
        """Record a page load."""
        self.total_page_loads += 1
        n = self.total_page_loads
        self.avg_initial_load_ms = (self.avg_initial_load_ms * (n - 1) + duration_ms) / n

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_page_loads": self.total_page_loads,
            "total_scrolls": self.total_scrolls,
            "total_device_clicks": self.total_device_clicks,
            "avg_initial_load_ms": f"{self.avg_initial_load_ms:.0f}",
            "active_subscriptions": self.active_subscriptions,
        }


# ============================================================================
# Page Device Manager - BACKWARD COMPATIBLE
# ============================================================================


class PageDeviceManager(QObject):
    """
    Page Device Manager - Backward compatible with progressive loading support.

    LEGACY MODE (config_path):
        manager = PageDeviceManager(config_path="path/to/config.json")
        - Loads page configurations from JSON file
        - Simple device list management
        - No progressive loading

    PROGRESSIVE MODE (with services):
        manager = PageDeviceManager(
            progressive_loader=loader,
            viewport_manager=viewport,
            status_service=status_service,
        )
        - 4-stage progressive loading
        - Viewport-based prefetching
        - Live update management

    Signals:
        page_changed: Emitted when page changes (page_id, device_ids)
        loading_progress: Emitted during load (progress 0.0-1.0)
        device_stage_changed: Progressive loading stage updates
    """

    # Qt Signals
    page_changed = Signal(str, list)  # page_id, device_ids
    loading_progress = Signal(float)  # progress 0.0 to 1.0
    device_stage_changed = Signal(str, object, object)  # device_id, stage, data

    def __init__(
        self,
        # Legacy parameters
        config_path: Optional[Union[str, Path]] = None,
        # Progressive parameters
        progressive_loader: Optional["ProgressiveDeviceLoader"] = None,
        viewport_manager: Optional["DeviceViewportManager"] = None,
        status_service: Optional["DeviceStatusService"] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        # Determine mode
        self._is_progressive_mode = progressive_loader is not None

        # Legacy mode config
        self._config_path = Path(config_path) if config_path else None
        self._config: Dict[str, Any] = {}
        self._pages_config: Dict[str, List[str]] = {}

        # Progressive mode services
        self._loader = progressive_loader
        self._viewport = viewport_manager
        self._status_service = status_service

        # Current state
        self._current_page: Optional[PageState] = None
        self._current_page_name: str = ""
        self._current_page_devices: List[str] = []

        # Live update management (progressive mode)
        self._live_update_tasks: Dict[str, asyncio.Task] = {}
        self._paused_devices: Set[str] = set()

        # Metrics
        self._metrics = PageMetrics()

        # Initialize based on mode
        if self._is_progressive_mode:
            self._init_progressive_mode()
        else:
            self._init_legacy_mode()

        logger.info(f"[PageDeviceManager] Initialized in " f"{'progressive' if self._is_progressive_mode else 'legacy'} mode")

    # ========================================================================
    # Initialization
    # ========================================================================

    def _init_legacy_mode(self) -> None:
        """Initialize legacy mode from config file."""
        if self._config_path and self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)

                # Extract page configurations
                self._parse_config()

                logger.info(f"[PageDeviceManager] Loaded config: " f"{len(self._pages_config)} pages")
            except Exception as e:
                logger.error(f"[PageDeviceManager] Config load failed: {e}")
                self._config = {}

    def _parse_config(self) -> None:
        """Parse device configurations from JSON - FIXED for assembly_midle_frame."""

        logger.debug(f"[PageDeviceManager] Config keys: {list(self._config.keys())}")

        # Process each area in config
        for area_key, area_config in self._config.items():
            if not isinstance(area_config, dict):
                continue

            # Determine page based on area key (simple keyword matching)
            area_lower = area_key.lower()

            if "assembly" in area_lower:
                page_name = "assembly_page"
            elif "electrode" in area_lower:
                page_name = "electrode_page"
            else:
                logger.debug(f"[PageDeviceManager] Skipping unknown area: {area_key}")
                continue

            # Extract devices from this area
            devices_section = area_config.get("devices", [])
            device_codes = []

            if isinstance(devices_section, list):
                for dev in devices_section:
                    if isinstance(dev, dict):
                        device_id = dev.get("id")
                        if device_id:
                            device_codes.append(device_id)
                    elif isinstance(dev, str):
                        device_codes.append(dev)

            # Add devices to the appropriate page
            if device_codes:
                if page_name not in self._pages_config:
                    self._pages_config[page_name] = []

                # Avoid duplicates
                existing = set(self._pages_config[page_name])
                new_devices = [d for d in device_codes if d not in existing]

                self._pages_config[page_name].extend(new_devices)

                logger.info(f"[PageDeviceManager] {area_key} -> {page_name}: " f"added {len(new_devices)} devices")

        # Final summary
        for page, devices in self._pages_config.items():
            logger.info(f"[PageDeviceManager] {page}: {len(devices)} total devices")

    def _init_progressive_mode(self) -> None:
        """Initialize progressive mode with services."""
        # Connect loader callbacks
        if self._loader:
            self._loader.on_stage_changed(self._on_device_stage_changed)

        # Connect viewport callbacks
        if self._viewport:
            self._viewport.on_visible_changed(self._on_visibility_changed)

    # ========================================================================
    # Legacy Mode API
    # ========================================================================

    def get_page_devices(self, page_name: str) -> List[str]:
        """
        Get device IDs for a page (Legacy API).

        Args:
            page_name: Page identifier

        Returns:
            List of device IDs for the page
        """
        return self._pages_config.get(page_name, [])

    def get_page_config(self, page_name: str) -> Dict[str, Any]:
        """
        Get full page configuration (Legacy API).

        Args:
            page_name: Page identifier

        Returns:
            Page configuration dict
        """
        if "pages" in self._config:
            return self._config["pages"].get(page_name, {})
        return self._config.get(page_name, {})

    def get_all_pages(self) -> List[str]:
        """Get all page names."""
        return list(self._pages_config.keys())

    def load_page(self, page_name: str, device_ids: Optional[List[str]] = None) -> None:
        """
        Load a page (Legacy API - synchronous).

        Args:
            page_name: Page identifier
            device_ids: Optional device IDs (uses config if None)
        """
        # Get device IDs from config if not provided
        if device_ids is None:
            device_ids = self.get_page_devices(page_name)

        self._current_page_name = page_name
        self._current_page_devices = device_ids.copy()

        # Create page state
        self._current_page = PageState(
            page_id=page_name,
            all_device_ids=device_ids,
            load_started_at=datetime.now(),
        )

        # Emit signal
        self.page_changed.emit(page_name, device_ids)

        logger.info(f"[PageDeviceManager] Loaded page: {page_name} " f"({len(device_ids)} devices)")

    # ========================================================================
    # Progressive Mode API
    # ========================================================================

    async def initial_load(
        self,
        page_id: str,
        all_device_ids: List[str],
        visible_positions: Optional[List[Tuple[str, int, int]]] = None,
    ) -> None:
        """
        Initial page load with progressive stages (Progressive API).

        Timeline:
        T+0ms    → Emit skeletons for all devices
        T+30ms   → Load visible devices (stale from cache)
        T+150ms  → Fetch visible devices (fresh from remote)
        T+200ms  → Start live updates for visible
        T+300ms  → Prefetch next devices in background

        Args:
            page_id: Page identifier
            all_device_ids: All devices on page
            visible_positions: Optional initial viewport positions
        """
        if not self._is_progressive_mode:
            # Fallback to legacy
            self.load_page(page_id, all_device_ids)
            return

        logger.info(f"[PageDeviceManager] Progressive load: {page_id} " f"({len(all_device_ids)} devices)")

        # Cleanup previous page
        if self._current_page:
            await self._cleanup_page(self._current_page)

        # Create new page state
        page = PageState(
            page_id=page_id,
            all_device_ids=all_device_ids,
            load_started_at=datetime.now(),
        )
        self._current_page = page
        self._current_page_name = page_id
        self._current_page_devices = all_device_ids.copy()

        # Emit page changed
        self.page_changed.emit(page_id, all_device_ids)

        # Determine visible devices
        visible_ids = all_device_ids[:15]  # Default to first 15

        if visible_positions and self._viewport:
            change = self._viewport.update_viewport(
                scroll_y=0,
                viewport_height=800,
                device_positions=visible_positions,
            )
            visible_ids = self._viewport.get_visible_devices()

        # Load visible devices
        page.visible_devices = set(visible_ids)

        if self._loader:
            await self._loader.load_batch(
                visible_ids,
                priority=self._get_high_priority(),
            )

        # Start live updates for visible
        await asyncio.sleep(0.05)
        await self._start_live_updates_batch(visible_ids)

        # Prefetch next devices
        if self._viewport:
            prefetch_ids = self._viewport.get_prefetch_devices()
            if prefetch_ids and self._loader:
                page.prefetch_devices = set(prefetch_ids)
                asyncio.create_task(
                    self._loader.load_batch(
                        prefetch_ids,
                        priority=self._get_low_priority(),
                    )
                )

        # Mark complete
        page.initial_load_completed_at = datetime.now()
        duration_ms = page.initial_load_duration_ms

        self._metrics.record_page_load(duration_ms)
        self.loading_progress.emit(1.0)

        logger.info(f"[PageDeviceManager] Load complete in {duration_ms:.0f}ms")

    def _get_high_priority(self):
        """Get high priority (avoid import at module level)."""
        try:
            from .progressive_loader import LoadPriority

            return LoadPriority.HIGH
        except ImportError:
            return None

    def _get_low_priority(self):
        """Get low priority (avoid import at module level)."""
        try:
            from .progressive_loader import LoadPriority

            return LoadPriority.LOW
        except ImportError:
            return None

    async def handle_scroll(
        self,
        scroll_y: int,
        viewport_height: int,
        device_positions: List[Tuple[str, int, int]],
    ) -> None:
        """
        Handle scroll event (Progressive API).

        Args:
            scroll_y: Current scroll position
            viewport_height: Viewport height in pixels
            device_positions: List of (device_id, top, height)
        """
        if not self._is_progressive_mode or not self._viewport:
            return

        self._metrics.total_scrolls += 1

        change = self._viewport.update_viewport(
            scroll_y,
            viewport_height,
            device_positions,
        )

        if not change.has_changes:
            return

        # Handle newly visible
        if change.newly_visible and self._loader:
            await self._loader.load_batch(
                change.newly_visible,
                priority=self._get_high_priority(),
            )
            await self._start_live_updates_batch(change.newly_visible)

        # Handle newly hidden
        if change.newly_hidden:
            await self._pause_live_updates_batch(change.newly_hidden)

        # Handle prefetch
        if change.entered_prefetch and self._loader:
            asyncio.create_task(
                self._loader.load_batch(
                    change.entered_prefetch,
                    priority=self._get_low_priority(),
                )
            )

    async def handle_device_click(
        self,
        device_id: str,
        is_double_click: bool = False,
    ) -> None:
        """Handle device click (Progressive API)."""
        self._metrics.total_device_clicks += 1

        if self._loader:
            try:
                from .progressive_loader import LoadPriority

                await self._loader.load_device(
                    device_id,
                    priority=LoadPriority.CRITICAL,
                    force_fresh=is_double_click,
                )
            except ImportError:
                pass

    # ========================================================================
    # Live Update Management
    # ========================================================================

    async def _start_live_updates_batch(self, device_ids: List[str]) -> None:
        """Start live updates for multiple devices."""
        if not self._is_progressive_mode:
            return

        for device_id in device_ids:
            await self._start_live_update(device_id)

    async def _start_live_update(self, device_id: str) -> None:
        """Start live update for a device."""
        if not self._current_page:
            return

        if device_id in self._current_page.live_subscriptions:
            return

        self._paused_devices.discard(device_id)
        self._current_page.live_subscriptions.add(device_id)
        self._metrics.active_subscriptions = len(self._current_page.live_subscriptions)

    async def _pause_live_updates_batch(self, device_ids: List[str]) -> None:
        """Pause live updates for multiple devices."""
        for device_id in device_ids:
            self._paused_devices.add(device_id)

    async def _stop_live_update(self, device_id: str) -> None:
        """Stop live update for a device."""
        if not self._current_page:
            return

        task = self._live_update_tasks.pop(device_id, None)
        if task and not task.done():
            task.cancel()

        self._current_page.live_subscriptions.discard(device_id)
        self._paused_devices.discard(device_id)

    # ========================================================================
    # Callbacks
    # ========================================================================

    def _on_device_stage_changed(
        self,
        device_id: str,
        stage: Any,
        data: Any,
    ) -> None:
        """Handle stage changes from progressive loader."""
        self.device_stage_changed.emit(device_id, stage, data)

        if self._current_page and stage:
            # Check if it's FRESH or LIVE stage
            stage_name = getattr(stage, "name", str(stage))
            if stage_name in ("FRESH", "LIVE"):
                self._current_page.loaded_devices.add(device_id)
                self.loading_progress.emit(self._current_page.load_progress)

    def _on_visibility_changed(self, change: Any) -> None:
        """Handle visibility changes from viewport manager."""
        pass  # Handled in handle_scroll

    # ========================================================================
    # Cleanup
    # ========================================================================

    async def _cleanup_page(self, page: PageState) -> None:
        """Cleanup resources for a page."""
        logger.debug(f"[PageDeviceManager] Cleaning up: {page.page_id}")

        for device_id in list(page.live_subscriptions):
            await self._stop_live_update(device_id)

        if self._loader:
            await self._loader.cancel_all()

        if self._viewport:
            self._viewport.clear()

        self._paused_devices.clear()

    async def dispose(self) -> None:
        """Dispose of manager resources."""
        if self._current_page:
            await self._cleanup_page(self._current_page)

        self._current_page = None
        self._live_update_tasks.clear()

        logger.info("[PageDeviceManager] Disposed")

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def current_page_name(self) -> str:
        """Get current page name."""
        return self._current_page_name

    @property
    def current_page_devices(self) -> List[str]:
        """Get current page device IDs."""
        return self._current_page_devices.copy()

    @property
    def is_progressive_mode(self) -> bool:
        """Check if using progressive loading mode."""
        return self._is_progressive_mode

    @property
    def config(self) -> Dict[str, Any]:
        """Get raw configuration (Legacy)."""
        return self._config

    def get_metrics(self) -> Dict[str, Any]:
        """Get manager metrics."""
        metrics = self._metrics.to_dict()

        if self._is_progressive_mode:
            if self._loader:
                metrics["loader"] = self._loader.get_metrics()
            if self._viewport:
                metrics["viewport"] = self._viewport.get_stats()

        return metrics

    def get_page_state(self) -> Optional[Dict[str, Any]]:
        """Get current page state."""
        if not self._current_page:
            return None

        return {
            "page_id": self._current_page.page_id,
            "total_devices": len(self._current_page.all_device_ids),
            "loaded_devices": len(self._current_page.loaded_devices),
            "visible_devices": len(self._current_page.visible_devices),
            "live_subscriptions": len(self._current_page.live_subscriptions),
            "load_progress": f"{self._current_page.load_progress:.1%}",
            "is_progressive": self._is_progressive_mode,
        }

    # ========================================================================
    # ADD THESE METHODS TO THE CLASS
    # ========================================================================

    def get_all_devices(self) -> List[str]:
        """
        Get all known device IDs across all pages.

        Returns:
            List of all unique device IDs
        """
        if self._is_progressive_mode:
            # Progressive mode: return from current page
            if self._current_page:
                return self._current_page.all_device_ids.copy()
            return []
        else:
            # Legacy mode: return all devices from config
            all_devices = set()

            # Collect from all pages
            for page_devices in self._pages_config.values():
                all_devices.update(page_devices)

            # Also check raw config for any devices section
            if isinstance(self._config, dict):
                # Check for devices at root level
                if "devices" in self._config:
                    devices = self._config["devices"]
                    if isinstance(devices, list):
                        for dev in devices:
                            if isinstance(dev, dict):
                                dev_id = dev.get("id", dev.get("device_id"))
                                if dev_id:
                                    all_devices.add(dev_id)
                            elif isinstance(dev, str):
                                all_devices.add(dev)

                # Check each area config
                for area_key, area_config in self._config.items():
                    if isinstance(area_config, dict) and "devices" in area_config:
                        devices = area_config["devices"]
                        if isinstance(devices, list):
                            for dev in devices:
                                if isinstance(dev, dict):
                                    dev_id = dev.get("id", dev.get("device_id"))
                                    if dev_id:
                                        all_devices.add(dev_id)
                                elif isinstance(dev, str):
                                    all_devices.add(dev)

            return list(all_devices)

    def force_load_current_page(self) -> List[str]:
        """
        Force emit page_changed signal for current page.

        Used for initial load when page hasn't changed but we need to
        trigger the signal for DeviceListViewModel to start loading.

        Returns:
            List of device IDs for current page
        """
        # Determine current page
        if not self._current_page_name:
            # Default to first available page or "electrode_page"
            if self._pages_config:
                self._current_page_name = list(self._pages_config.keys())[0]
            else:
                self._current_page_name = "electrode_page"

        # Get devices for current page
        if self._is_progressive_mode:
            devices = self._current_page_devices or []
        else:
            devices = self.get_page_devices(self._current_page_name)

        logger.info(f"[PageDeviceManager] Force loading {self._current_page_name}: " f"{len(devices)} devices")

        # Update state
        if not self._current_page_devices:
            self._current_page_devices = devices.copy()

        # Emit signal
        self.page_changed.emit(self._current_page_name, devices)

        return devices

    def get_all_page_devices(self) -> Dict[str, List[str]]:
        """
        Get all page-to-devices mappings.

        Returns:
            Dict mapping page_name to list of device_ids
        """
        if self._is_progressive_mode:
            # Progressive mode: return current page only
            if self._current_page:
                return {self._current_page.page_id: self._current_page.all_device_ids}
            return {}
        else:
            # Legacy mode: return all pages from config
            return self._pages_config.copy()

    def get_all_page_names(self) -> List[str]:
        """
        Get list of all configured page names.

        Returns:
            List of page names
        """
        if self._is_progressive_mode:
            # Progressive mode
            if self._current_page:
                return [self._current_page.page_id]
            return []
        else:
            # Legacy mode
            return list(self._pages_config.keys())

    def get_device_count(self, page_name: Optional[str] = None) -> int:
        """
        Get device count for a page or all pages.

        Args:
            page_name: Page name, or None for total count

        Returns:
            Device count
        """
        if page_name:
            return len(self.get_page_devices(page_name))
        else:
            return len(self.get_all_devices())

    def set_current_page(self, page_name: str) -> List[str]:
        """
        Set current page and emit signal.

        Args:
            page_name: Page to switch to

        Returns:
            List of device IDs for the page
        """
        self._current_page_name = page_name
        devices = self.get_page_devices(page_name)

        logger.info(f"[PageDeviceManager] Page changed to {page_name}: " f"{len(devices)} devices")

        # Update state
        self._current_page_devices = devices.copy()

        # Emit signal
        self.page_changed.emit(page_name, devices)

        return devices

    def get_current_page(self) -> str:
        """Get the current page name."""
        return self._current_page_name or "electrode_page"

    def get_current_devices(self) -> List[str]:
        """Get device IDs for the current page."""
        return self._current_page_devices.copy()

    def get_layout_config(self, area_key: str) -> Dict[str, Any]:
        """
        Get raw layout config for an area key.

        Args:
            area_key: Area identifier from config

        Returns:
            Layout configuration dict
        """
        if isinstance(self._config, dict):
            return self._config.get(area_key, {})
        return {}

    def get_page_layout_configs(self, page_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all layout configs for areas on a page.

        Args:
            page_name: Page name

        Returns:
            Dict mapping area_key to layout config
        """
        configs = {}

        # Map page names to area keys
        if page_name == "electrode_page" or page_name == "daboard_page":
            # Check for electrode-related areas
            for key in ["electrode", "daboard", "electrode_area"]:
                if key in self._config:
                    configs[key] = self._config[key]

        elif page_name == "assembly_page":
            # Check for assembly-related areas
            for key in ["assembly", "assembly_area", "order"]:
                if key in self._config:
                    configs[key] = self._config[key]

        return configs

    def is_device_on_page(self, device_id: str, page_name: str) -> bool:
        """
        Check if a device belongs to a page.

        Args:
            device_id: Device identifier
            page_name: Page name

        Returns:
            True if device is on page
        """
        page_devices = self.get_page_devices(page_name)
        return device_id in page_devices

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.

        Returns:
            Dict with statistics
        """
        all_devices = self.get_all_devices()

        stats = {
            "current_page": self.get_current_page(),
            "total_pages": len(self.get_all_page_names()),
            "total_devices": len(all_devices),
            "current_page_devices": len(self.get_current_devices()),
            "is_progressive": self._is_progressive_mode,
        }

        # Add per-page stats
        if not self._is_progressive_mode:
            stats["pages"] = {name: len(devices) for name, devices in self._pages_config.items()}

        return stats

    # ========================================================================
    # Properties (keep existing ones and add these)
    # ========================================================================

    @property
    def current_page(self) -> str:
        """Get current page name (property for compatibility)."""
        return self.get_current_page()

    @current_page.setter
    def current_page(self, value: str) -> None:
        """Set current page name (property for compatibility)."""
        self.set_current_page(value)


__all__ = [
    "PageDeviceManager",
    "PageState",
    "PageMetrics",
]
