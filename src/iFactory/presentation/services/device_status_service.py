# File: src/iFactory/presentation/services/device_status_service.py
"""
Device Status Service - Single Source of Truth for device status.

This service provides:
1. Centralized status management for all devices
2. Real-time status updates via signals
3. Thread-safe access
4. Caching with configurable TTL
5. Status change history tracking
6. Integration with both DeviceListViewModel and GanttChartViewModel

Architecture:
    DeviceListViewModel ─────┐
                             │
                             ▼
                    DeviceStatusService ◄───── Single Source of Truth
                             │
                             ▼
    GanttChartViewModel ◄────┘
    DeviceCanvas ◄───────────┘
    GanttWidget ◄────────────┘

Usage:
    # Get service instance
    service = DeviceStatusService.instance()

    # Update status (from DeviceListViewModel)
    service.update_device_status("DEV01", 1, "Running", "#2ECC71")

    # Get current status (from any component)
    status = service.get_device_status("DEV01")

    # Subscribe to changes
    service.statusChanged.connect(on_status_changed)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple
from weakref import WeakSet

from PySide6.QtCore import QObject, Signal, Slot, QTimer

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


@dataclass(frozen=True, slots=True)
class DeviceStatus:
    """
    Immutable device status snapshot.

    Attributes:
        device_id: Unique device identifier
        status_code: Numeric status code (1=Running, 2=Shutdown, 3=Stopped, etc.)
        status_name: Human-readable status name
        status_color: Color for UI rendering
        timestamp: When this status was recorded
        is_stale: Whether this status is potentially outdated
    """

    device_id: str
    status_code: int
    status_name: str
    status_color: str
    timestamp: datetime = field(default_factory=datetime.now)
    is_stale: bool = False

    @property
    def is_running(self) -> bool:
        return self.status_code == 1

    @property
    def is_stopped(self) -> bool:
        return self.status_code == 3

    @property
    def is_alarm(self) -> bool:
        return self.status_code == 5

    @property
    def age_seconds(self) -> float:
        """Seconds since this status was recorded."""
        return (datetime.now() - self.timestamp).total_seconds()

    def with_stale_flag(self, is_stale: bool) -> "DeviceStatus":
        """Create new instance with updated stale flag."""
        return DeviceStatus(
            device_id=self.device_id,
            status_code=self.status_code,
            status_name=self.status_name,
            status_color=self.status_color,
            timestamp=self.timestamp,
            is_stale=is_stale,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "device_id": self.device_id,
            "status_code": self.status_code,
            "status_name": self.status_name,
            "status_color": self.status_color,
            "timestamp": self.timestamp.isoformat(),
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceStatus":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        return cls(
            device_id=data.get("device_id", ""),
            status_code=int(data.get("status_code", 0)),
            status_name=data.get("status_name", "Unknown"),
            status_color=data.get("status_color", "#9E9E9E"),
            timestamp=timestamp,
            is_stale=data.get("is_stale", False),
        )

    @classmethod
    def unknown(cls, device_id: str) -> "DeviceStatus":
        """Create unknown status for device."""
        return cls(
            device_id=device_id,
            status_code=0,
            status_name="Unknown",
            status_color="#9E9E9E",
            is_stale=True,
        )


@dataclass(frozen=True, slots=True)
class StatusChange:
    """
    Record of a status change event.

    Used for:
    - Animation triggers
    - Audit logging
    - Status history tracking
    """

    device_id: str
    old_status: DeviceStatus
    new_status: DeviceStatus
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def status_code_changed(self) -> bool:
        return self.old_status.status_code != self.new_status.status_code

    @property
    def old_code(self) -> int:
        return self.old_status.status_code

    @property
    def new_code(self) -> int:
        return self.new_status.status_code


@dataclass
class ServiceMetrics:
    """Metrics for the status service."""

    total_updates: int = 0
    status_changes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    stale_checks: int = 0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_updates": self.total_updates,
            "status_changes": self.status_changes,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{self.cache_hit_rate:.1f}%",
        }


# ============================================================================
# Status Constants (centralized)
# ============================================================================


class StatusCode:
    """Status code constants."""

    UNKNOWN = 0
    RUNNING = 1
    SHUTDOWN = 2
    STOPPED = 3
    MAINTENANCE = 4
    ALARM = 5


class StatusInfo:
    """Status information lookup."""

    _STATUS_MAP: Dict[int, Tuple[str, str]] = {
        StatusCode.UNKNOWN: ("Unknown", "#9E9E9E"),
        StatusCode.RUNNING: ("Running", "#2ECC71"),
        StatusCode.SHUTDOWN: ("Shutdown", "#7F8C8D"),
        StatusCode.STOPPED: ("Stopped", "#E74C3C"),
        StatusCode.MAINTENANCE: ("Maintenance", "#9B59B6"),
        StatusCode.ALARM: ("Alarm", "#F1C40F"),
    }

    @classmethod
    def get_name(cls, code: int) -> str:
        """Get status name for code."""
        info = cls._STATUS_MAP.get(code, cls._STATUS_MAP[StatusCode.UNKNOWN])
        return info[0]

    @classmethod
    def get_color(cls, code: int) -> str:
        """Get status color for code."""
        info = cls._STATUS_MAP.get(code, cls._STATUS_MAP[StatusCode.UNKNOWN])
        return info[1]

    @classmethod
    def get_info(cls, code: int) -> Tuple[str, str]:
        """Get (name, color) tuple for code."""
        return cls._STATUS_MAP.get(code, cls._STATUS_MAP[StatusCode.UNKNOWN])


# ============================================================================
# Device Status Service
# ============================================================================


class DeviceStatusService(QObject):
    """
    Singleton service for centralized device status management.

    Features:
    - Thread-safe status storage
    - Real-time change notifications
    - Configurable stale data detection
    - Status change history
    - Batch update support
    - Metrics tracking

    Signals:
        statusChanged: Emitted when any device status changes
        statusUpdated: Emitted on any status update (even if unchanged)
        batchUpdated: Emitted after batch update completes
        staleDevicesDetected: Emitted when stale devices are found

    Thread Safety:
        All public methods are thread-safe via RLock.
    """

    # Signals
    statusChanged = Signal(str, object)  # device_id, StatusChange
    statusUpdated = Signal(str, object)  # device_id, DeviceStatus
    batchUpdated = Signal(dict)  # {device_id: DeviceStatus}
    staleDevicesDetected = Signal(list)  # List[str] of stale device IDs

    # Configuration
    STALE_THRESHOLD_SECONDS: float = 30.0
    HISTORY_MAX_SIZE: int = 1000
    STALE_CHECK_INTERVAL_MS: int = 10000

    # Singleton instance
    _instance: Optional["DeviceStatusService"] = None
    _instance_lock = RLock()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Storage
        self._statuses: Dict[str, DeviceStatus] = {}
        self._change_history: List[StatusChange] = []
        self._lock = RLock()

        # Metrics
        self._metrics = ServiceMetrics()

        # Stale detection timer
        self._stale_timer: Optional[QTimer] = None
        self._setup_stale_timer()

        # Subscribers (weak references to prevent memory leaks)
        self._subscribers: WeakSet = WeakSet()

        logger.info("[DeviceStatusService] Initialized")

    @classmethod
    def instance(cls) -> "DeviceStatusService":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.dispose()
                cls._instance = None

    def _setup_stale_timer(self) -> None:
        """Setup timer for periodic stale checks."""
        self._stale_timer = QTimer(self)
        self._stale_timer.timeout.connect(self._check_stale_devices)
        self._stale_timer.start(self.STALE_CHECK_INTERVAL_MS)

    # ========================================================================
    # Public API: Status Updates
    # ========================================================================

    def update_device_status(
        self,
        device_id: str,
        status_code: int,
        status_name: Optional[str] = None,
        status_color: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Optional[StatusChange]:
        """
        Update status for a single device.

        Args:
            device_id: Device identifier
            status_code: New status code
            status_name: Optional status name (auto-resolved if None)
            status_color: Optional status color (auto-resolved if None)
            timestamp: Optional timestamp (defaults to now)

        Returns:
            StatusChange if status code changed, None otherwise
        """
        if not device_id:
            return None

        # Resolve status info
        if status_name is None or status_color is None:
            resolved_name, resolved_color = StatusInfo.get_info(status_code)
            status_name = status_name or resolved_name
            status_color = status_color or resolved_color

        new_status = DeviceStatus(
            device_id=device_id,
            status_code=status_code,
            status_name=status_name,
            status_color=status_color,
            timestamp=timestamp or datetime.now(),
            is_stale=False,
        )

        with self._lock:
            self._metrics.total_updates += 1

            old_status = self._statuses.get(device_id)
            self._statuses[device_id] = new_status

            # Check if status code changed
            change: Optional[StatusChange] = None
            if old_status and old_status.status_code != new_status.status_code:
                change = StatusChange(
                    device_id=device_id,
                    old_status=old_status,
                    new_status=new_status,
                )
                self._record_change(change)
                self._metrics.status_changes += 1

        # Emit signals outside lock
        self.statusUpdated.emit(device_id, new_status)
        if change:
            self.statusChanged.emit(device_id, change)
            logger.debug(f"[DeviceStatusService] Status changed: {device_id} " f"{change.old_code} → {change.new_code}")

        return change

    def update_batch(
        self,
        updates: Dict[str, Dict[str, Any]],
        emit_individual: bool = False,
    ) -> List[StatusChange]:
        """
        Batch update multiple device statuses.

        Args:
            updates: Dict of {device_id: {status_code, status_name?, status_color?}}
            emit_individual: Whether to emit individual statusChanged signals

        Returns:
            List of StatusChange for devices that changed
        """
        changes: List[StatusChange] = []
        updated_statuses: Dict[str, DeviceStatus] = {}

        with self._lock:
            for device_id, data in updates.items():
                if not device_id:
                    continue

                status_code = data.get("status_code", 0)
                if isinstance(status_code, str):
                    try:
                        status_code = int(status_code)
                    except ValueError:
                        status_code = 0

                status_name = data.get("status_name")
                status_color = data.get("status_color")

                if status_name is None or status_color is None:
                    resolved_name, resolved_color = StatusInfo.get_info(status_code)
                    status_name = status_name or resolved_name
                    status_color = status_color or resolved_color

                new_status = DeviceStatus(
                    device_id=device_id,
                    status_code=status_code,
                    status_name=status_name,
                    status_color=status_color,
                    timestamp=datetime.now(),
                    is_stale=False,
                )

                old_status = self._statuses.get(device_id)
                self._statuses[device_id] = new_status
                updated_statuses[device_id] = new_status
                self._metrics.total_updates += 1

                if old_status and old_status.status_code != new_status.status_code:
                    change = StatusChange(
                        device_id=device_id,
                        old_status=old_status,
                        new_status=new_status,
                    )
                    changes.append(change)
                    self._record_change(change)
                    self._metrics.status_changes += 1

        # Emit signals outside lock
        if emit_individual:
            for change in changes:
                self.statusChanged.emit(change.device_id, change)

        self.batchUpdated.emit(updated_statuses)

        if changes:
            logger.info(f"[DeviceStatusService] Batch update: {len(updates)} devices, " f"{len(changes)} changes")

        return changes

    # ========================================================================
    # Public API: Status Retrieval
    # ========================================================================

    def get_device_status(self, device_id: str) -> Optional[DeviceStatus]:
        """
        Get current status for a device.

        Returns None if device not found.
        """
        with self._lock:
            status = self._statuses.get(device_id)
            if status:
                self._metrics.cache_hits += 1
            else:
                self._metrics.cache_misses += 1
            return status

    def get_device_status_or_unknown(self, device_id: str) -> DeviceStatus:
        """
        Get current status for a device, or Unknown status if not found.
        """
        status = self.get_device_status(device_id)
        return status if status else DeviceStatus.unknown(device_id)

    def get_status_code(self, device_id: str) -> int:
        """Get status code for device (0 if not found)."""
        status = self.get_device_status(device_id)
        return status.status_code if status else 0

    def get_status_color(self, device_id: str) -> str:
        """Get status color for device."""
        status = self.get_device_status(device_id)
        return status.status_color if status else "#9E9E9E"

    def get_status_name(self, device_id: str) -> str:
        """Get status name for device."""
        status = self.get_device_status(device_id)
        return status.status_name if status else "Unknown"

    def get_all_statuses(self) -> Dict[str, DeviceStatus]:
        """Get all device statuses (copy)."""
        with self._lock:
            return dict(self._statuses)

    def get_devices_by_status(self, status_code: int) -> List[str]:
        """Get list of device IDs with given status code."""
        with self._lock:
            return [device_id for device_id, status in self._statuses.items() if status.status_code == status_code]

    def has_device(self, device_id: str) -> bool:
        """Check if device exists in service."""
        with self._lock:
            return device_id in self._statuses

    # ========================================================================
    # Public API: Status History
    # ========================================================================

    def get_recent_changes(
        self,
        since: Optional[datetime] = None,
        device_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[StatusChange]:
        """
        Get recent status changes.

        Args:
            since: Only return changes after this time
            device_id: Filter by device ID
            limit: Maximum number of changes to return
        """
        with self._lock:
            changes = self._change_history.copy()

        if since:
            changes = [c for c in changes if c.timestamp >= since]

        if device_id:
            changes = [c for c in changes if c.device_id == device_id]

        return changes[-limit:]

    def get_last_change(self, device_id: str) -> Optional[StatusChange]:
        """Get the most recent change for a device."""
        with self._lock:
            for change in reversed(self._change_history):
                if change.device_id == device_id:
                    return change
        return None

    # ========================================================================
    # Public API: Stale Detection
    # ========================================================================

    def get_stale_devices(self) -> List[str]:
        """Get list of devices with stale status."""
        with self._lock:
            self._metrics.stale_checks += 1
            threshold = self.STALE_THRESHOLD_SECONDS
            return [device_id for device_id, status in self._statuses.items() if status.age_seconds > threshold]

    def is_device_stale(self, device_id: str) -> bool:
        """Check if device status is stale."""
        status = self.get_device_status(device_id)
        if not status:
            return True
        return status.age_seconds > self.STALE_THRESHOLD_SECONDS

    def mark_device_stale(self, device_id: str) -> None:
        """Manually mark a device as stale."""
        with self._lock:
            if device_id in self._statuses:
                old_status = self._statuses[device_id]
                self._statuses[device_id] = old_status.with_stale_flag(True)

    @Slot()
    def _check_stale_devices(self) -> None:
        """Periodic check for stale devices."""
        stale = self.get_stale_devices()
        if stale:
            self.staleDevicesDetected.emit(stale)

    # ========================================================================
    # Public API: Cleanup
    # ========================================================================

    def remove_device(self, device_id: str) -> bool:
        """Remove a device from the service."""
        with self._lock:
            if device_id in self._statuses:
                del self._statuses[device_id]
                return True
            return False

    def clear_all(self) -> None:
        """Clear all device statuses."""
        with self._lock:
            self._statuses.clear()
            self._change_history.clear()
        logger.info("[DeviceStatusService] Cleared all statuses")

    def clear_devices(self, device_ids: List[str]) -> int:
        """Clear specific devices. Returns number removed."""
        count = 0
        with self._lock:
            for device_id in device_ids:
                if device_id in self._statuses:
                    del self._statuses[device_id]
                    count += 1
        return count

    # ========================================================================
    # Public API: Metrics
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        with self._lock:
            return {
                **self._metrics.to_dict(),
                "device_count": len(self._statuses),
                "history_size": len(self._change_history),
            }

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        with self._lock:
            self._metrics = ServiceMetrics()

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _record_change(self, change: StatusChange) -> None:
        """Record a status change (must be called with lock held)."""
        self._change_history.append(change)

        # Trim history if too large
        if len(self._change_history) > self.HISTORY_MAX_SIZE:
            self._change_history = self._change_history[-self.HISTORY_MAX_SIZE :]

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
        if self._stale_timer:
            self._stale_timer.stop()
            self._stale_timer = None

        with self._lock:
            self._statuses.clear()
            self._change_history.clear()

        logger.info("[DeviceStatusService] Disposed")


# ============================================================================
# Helper Functions
# ============================================================================


def get_device_status_service() -> DeviceStatusService:
    """Get the device status service singleton."""
    return DeviceStatusService.instance()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Service
    "DeviceStatusService",
    "get_device_status_service",
    # Models
    "DeviceStatus",
    "StatusChange",
    "ServiceMetrics",
    # Constants
    "StatusCode",
    "StatusInfo",
]
