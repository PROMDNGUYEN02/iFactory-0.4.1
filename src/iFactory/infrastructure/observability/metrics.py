# src/iFactory/infrastructure/observability/metrics.py
"""
Metrics collection for application monitoring.

Features:
- Counter, Gauge, Histogram metrics
- Timer context manager and decorator
- Tag-based labeling
- Thread-safe operations
- Global metrics registry
"""

from __future__ import annotations

import functools
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

T = TypeVar("T")


# ============================================================================
# Metric Value
# ============================================================================


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A single metric measurement."""

    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
        }


# ============================================================================
# Base Metric
# ============================================================================


class Metric(ABC):
    """Base class for all metrics."""

    __slots__ = ("_name", "_description", "_lock")

    def __init__(self, name: str, description: str = "") -> None:
        self._name = name
        self._description = description
        self._lock = Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @abstractmethod
    def collect(self) -> List[MetricValue]:
        """Collect current metric values."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset metric to initial state."""
        pass

    def _make_key(self, tags: Optional[Dict[str, str]]) -> tuple:
        """Create hashable key from tags."""
        return tuple(sorted((tags or {}).items()))


# ============================================================================
# Counter
# ============================================================================


class Counter(Metric):
    """
    Counter metric that only goes up.

    Usage:
        counter = Counter("requests_total", "Total HTTP requests")
        counter.inc()
        counter.inc(5)
        counter.inc(tags={"method": "GET", "status": "200"})
    """

    __slots__ = ("_values",)

    def __init__(self, name: str, description: str = "") -> None:
        super().__init__(name, description)
        self._values: Dict[tuple, float] = defaultdict(float)

    def inc(
        self,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment counter by value (default 1)."""
        if value < 0:
            raise ValueError("Counter can only be incremented")
        key = self._make_key(tags)
        with self._lock:
            self._values[key] += value

    def get(self, tags: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        key = self._make_key(tags)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(
                    name=self._name,
                    value=value,
                    tags=dict(key),
                )
                for key, value in self._values.items()
            ]

    def reset(self) -> None:
        with self._lock:
            self._values.clear()


# ============================================================================
# Gauge
# ============================================================================


class Gauge(Metric):
    """
    Gauge metric that can go up and down.

    Usage:
        gauge = Gauge("active_connections", "Currently active connections")
        gauge.set(10)
        gauge.inc()
        gauge.dec()
        gauge.set(5, tags={"server": "web-1"})
    """

    __slots__ = ("_values",)

    def __init__(self, name: str, description: str = "") -> None:
        super().__init__(name, description)
        self._values: Dict[tuple, float] = defaultdict(float)

    def set(
        self,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set gauge to specific value."""
        key = self._make_key(tags)
        with self._lock:
            self._values[key] = value

    def inc(
        self,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment gauge."""
        key = self._make_key(tags)
        with self._lock:
            self._values[key] += value

    def dec(
        self,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Decrement gauge."""
        key = self._make_key(tags)
        with self._lock:
            self._values[key] -= value

    def get(self, tags: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        key = self._make_key(tags)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> List[MetricValue]:
        with self._lock:
            return [
                MetricValue(
                    name=self._name,
                    value=value,
                    tags=dict(key),
                )
                for key, value in self._values.items()
            ]

    def reset(self) -> None:
        with self._lock:
            self._values.clear()


# ============================================================================
# Histogram
# ============================================================================


@dataclass
class HistogramData:
    """Internal histogram data for a label set."""

    buckets: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0


class Histogram(Metric):
    """
    Histogram for measuring distributions.

    Usage:
        histogram = Histogram(
            "request_duration_seconds",
            "Request duration",
            buckets=(0.1, 0.5, 1.0, 5.0)
        )
        histogram.observe(0.3)
        histogram.observe(1.5, tags={"endpoint": "/api/users"})
    """

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    __slots__ = ("_buckets", "_data")

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
    ) -> None:
        super().__init__(name, description)
        self._buckets = tuple(sorted(buckets or self.DEFAULT_BUCKETS))
        self._data: Dict[tuple, HistogramData] = {}

    def observe(
        self,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record an observation."""
        key = self._make_key(tags)
        with self._lock:
            if key not in self._data:
                self._data[key] = HistogramData(buckets={b: 0 for b in self._buckets})

            data = self._data[key]
            data.sum += value
            data.count += 1

            for bucket in self._buckets:
                if value <= bucket:
                    data.buckets[bucket] += 1

    def get_percentile(
        self,
        percentile: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[float]:
        """Estimate percentile value (approximate)."""
        key = self._make_key(tags)
        with self._lock:
            data = self._data.get(key)
            if not data or data.count == 0:
                return None

            target = data.count * percentile / 100.0
            cumulative = 0
            prev_bucket = 0.0

            for bucket in self._buckets:
                cumulative = data.buckets[bucket]
                if cumulative >= target:
                    return bucket
                prev_bucket = bucket

            return self._buckets[-1]

    def collect(self) -> List[MetricValue]:
        values = []
        with self._lock:
            for key, data in self._data.items():
                tags = dict(key)

                # Sum
                values.append(
                    MetricValue(
                        name=f"{self._name}_sum",
                        value=data.sum,
                        tags=tags,
                    )
                )

                # Count
                values.append(
                    MetricValue(
                        name=f"{self._name}_count",
                        value=float(data.count),
                        tags=tags,
                    )
                )

                # Buckets (cumulative)
                cumulative = 0
                for bucket in self._buckets:
                    cumulative = data.buckets[bucket]
                    values.append(
                        MetricValue(
                            name=f"{self._name}_bucket",
                            value=float(cumulative),
                            tags={**tags, "le": str(bucket)},
                        )
                    )

                # +Inf bucket
                values.append(
                    MetricValue(
                        name=f"{self._name}_bucket",
                        value=float(data.count),
                        tags={**tags, "le": "+Inf"},
                    )
                )

        return values

    def reset(self) -> None:
        with self._lock:
            self._data.clear()


# ============================================================================
# Timer
# ============================================================================


class Timer:
    """
    Context manager for timing operations.

    Usage:
        histogram = Histogram("operation_duration")

        with Timer(histogram):
            do_work()

        # With tags
        with Timer(histogram, tags={"operation": "fetch"}):
            fetch_data()
    """

    __slots__ = ("_histogram", "_tags", "_start")

    def __init__(
        self,
        histogram: Histogram,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        self._histogram = histogram
        self._tags = tags
        self._start: Optional[float] = None

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._start is not None:
            duration = time.perf_counter() - self._start
            self._histogram.observe(duration, self._tags)

    @property
    def elapsed(self) -> float:
        """Get elapsed time so far."""
        if self._start is None:
            return 0.0
        return time.perf_counter() - self._start


def timer(
    histogram: Histogram,
    tags: Optional[Dict[str, str]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for timing functions.

    Usage:
        @timer(request_duration, tags={"endpoint": "/api"})
        def handle_request():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with Timer(histogram, tags):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# Metrics Collector
# ============================================================================


class MetricsCollector:
    """
    Central collector for all metrics.

    Usage:
        collector = MetricsCollector()

        # Create metrics
        requests = collector.counter("requests_total", "Total requests")
        active = collector.gauge("active_connections", "Active connections")
        duration = collector.histogram("request_duration", "Request duration")

        # Use metrics
        requests.inc(tags={"method": "GET"})
        active.set(42)
        duration.observe(0.123)

        # Collect all
        all_values = collector.collect_all()
        summary = collector.to_dict()
    """

    __slots__ = ("_metrics", "_lock", "_created_at")

    def __init__(self) -> None:
        self._metrics: Dict[str, Metric] = {}
        self._lock = Lock()
        self._created_at = datetime.now()

    def counter(
        self,
        name: str,
        description: str = "",
    ) -> Counter:
        """Get or create a counter."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description)
            metric = self._metrics[name]
            if not isinstance(metric, Counter):
                raise TypeError(f"Metric '{name}' is not a Counter")
            return metric

    def gauge(
        self,
        name: str,
        description: str = "",
    ) -> Gauge:
        """Get or create a gauge."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description)
            metric = self._metrics[name]
            if not isinstance(metric, Gauge):
                raise TypeError(f"Metric '{name}' is not a Gauge")
            return metric

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
    ) -> Histogram:
        """Get or create a histogram."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, description, buckets)
            metric = self._metrics[name]
            if not isinstance(metric, Histogram):
                raise TypeError(f"Metric '{name}' is not a Histogram")
            return metric

    def collect_all(self) -> List[MetricValue]:
        """Collect all metric values."""
        values = []
        with self._lock:
            for metric in self._metrics.values():
                values.extend(metric.collect())
        return values

    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for metric in self._metrics.values():
                metric.reset()

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        result: Dict[str, Any] = {}
        for value in self.collect_all():
            key = value.name
            if value.tags:
                tag_str = ",".join(f'{k}="{v}"' for k, v in sorted(value.tags.items()))
                key = f"{key}{{{tag_str}}}"
            result[key] = value.value
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of metrics collector."""
        with self._lock:
            return {
                "uptime_seconds": (datetime.now() - self._created_at).total_seconds(),
                "metric_count": len(self._metrics),
                "metrics": list(self._metrics.keys()),
            }


# ============================================================================
# Global Instance
# ============================================================================

_metrics: Optional[MetricsCollector] = None
_metrics_lock = Lock()


def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    global _metrics
    with _metrics_lock:
        if _metrics is None:
            _metrics = MetricsCollector()
        return _metrics


def reset_metrics() -> None:
    """Reset global metrics collector."""
    global _metrics
    with _metrics_lock:
        if _metrics:
            _metrics.reset_all()
        _metrics = None


__all__ = [
    # Types
    "Metric",
    "MetricValue",
    # Metrics
    "Counter",
    "Gauge",
    "Histogram",
    # Timer
    "Timer",
    "timer",
    # Collector
    "MetricsCollector",
    "get_metrics",
    "reset_metrics",
]
