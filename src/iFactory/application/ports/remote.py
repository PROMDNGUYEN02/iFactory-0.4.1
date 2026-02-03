# src/iFactory/application/ports/remote.py
"""
Remote Data Source Port.
Interface for external data sources (MSSQL, API, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from typing import Any, Dict, List, Optional


class ConnectionState(StrEnum):
    """Connection state for remote source."""

    CONNECTED = auto()
    DISCONNECTED = auto()
    CONNECTING = auto()
    ERROR = auto()


@dataclass
class RemoteHealthStatus:
    """Health status for remote data source."""

    state: ConnectionState = ConnectionState.DISCONNECTED
    latency_ms: float = 0.0
    last_check: datetime = field(default_factory=datetime.now)
    message: str = ""
    consecutive_failures: int = 0

    @property
    def is_healthy(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
            "message": self.message,
            "consecutive_failures": self.consecutive_failures,
            "is_healthy": self.is_healthy,
        }


@dataclass
class RemoteMetrics:
    """Metrics for remote data source operations."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_success(self, latency_ms: float) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.last_request_time = datetime.now()

    def record_failure(self) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.last_request_time = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{self.success_rate:.2%}",
            "avg_latency_ms": f"{self.avg_latency_ms:.1f}",
            "last_request_time": (self.last_request_time.isoformat() if self.last_request_time else None),
        }


class IRemoteDataSource(ABC):
    """Port interface for remote data sources."""

    @abstractmethod
    async def fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest status for specified devices.
        If equipment_codes is None, fetch all devices.
        """
        pass

    @abstractmethod
    async def fetch_device_status(
        self,
        equip_code: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Fetch history status for a single device."""
        pass

    @abstractmethod
    async def fetch_device_history_range(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch history for a specific time range."""
        pass

    @abstractmethod
    async def fetch_latest_history_records(
        self,
        equip_code: str,
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the N most recent history records for a device.
        Used for incremental sync (upsert).
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up resources."""
        pass

    # Non-abstract methods with default implementations
    @property
    def is_available(self) -> bool:
        """Check if source is currently available."""
        return True

    async def health_check(self) -> RemoteHealthStatus:
        """Perform health check on the remote source."""
        return RemoteHealthStatus(state=ConnectionState.CONNECTED)

    def get_metrics(self) -> RemoteMetrics:
        """Get operation metrics."""
        return RemoteMetrics()


__all__ = [
    "IRemoteDataSource",
    "ConnectionState",
    "RemoteHealthStatus",
    "RemoteMetrics",
]
