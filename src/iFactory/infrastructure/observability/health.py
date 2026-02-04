# src/iFactory/infrastructure/observability/health.py
"""Health check infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


class HealthCheck(ABC):
    """Base class for health checks."""

    def __init__(self, name: str, critical: bool = True) -> None:
        self.name = name
        self.critical = critical

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        pass


class HealthRegistry:
    """Registry for health checks."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}

    def register(self, check: HealthCheck) -> None:
        self._checks[check.name] = check

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)

    async def check_all(self) -> dict[str, HealthCheckResult]:
        results: dict[str, HealthCheckResult] = {}
        for name, check in self._checks.items():
            try:
                results[name] = await check.check()
            except Exception as e:
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}",
                )
        return results

    async def get_overall_status(self) -> HealthStatus:
        results = await self.check_all()
        if not results:
            return HealthStatus.HEALTHY

        critical_statuses = [r.status for name, r in results.items() if self._checks.get(name, HealthCheck("", False)).critical]

        if any(s == HealthStatus.UNHEALTHY for s in critical_statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in critical_statuses):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def list_checks(self) -> list[str]:
        return list(self._checks.keys())


_registry: HealthRegistry | None = None


def get_health_registry() -> HealthRegistry:
    """Get global health registry."""
    global _registry
    if _registry is None:
        _registry = HealthRegistry()
    return _registry


__all__ = [
    "HealthCheck",
    "HealthCheckResult",
    "HealthRegistry",
    "HealthStatus",
    "get_health_registry",
]
