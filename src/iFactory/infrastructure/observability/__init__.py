# src/infrastructure/observability/__init__.py
"""
Observability infrastructure for monitoring and debugging.

Features:
- Structured logging
- Metrics collection
- Distributed tracing (preparatory)
- Health checks
"""

from .logging import (
    configure_logging,
    StructuredLogger,
    get_logger,
    LogContext,
)
from .metrics import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    Timer,
    get_metrics,
)
from .health import (
    HealthCheck,
    HealthRegistry,
    HealthStatus,
    get_health_registry,
)

__all__ = [
    # Logging
    "configure_logging",
    "StructuredLogger",
    "get_logger",
    "LogContext",
    # Metrics
    "MetricsCollector",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "get_metrics",
    # Health
    "HealthCheck",
    "HealthRegistry",
    "HealthStatus",
    "get_health_registry",
]
