# src/infrastructure/observability/metrics.py
"""
Metrics collection for application monitoring.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")


@dataclass
class MetricValue:
    """A single metric measurement."""

    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


class Metric(ABC):
    """Base class for metrics."""

    def __init__(self, name: str, description: str = ""):
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def collect(self) -> List[MetricValue]:
        """Collect current metric values."""
        pass


class Counter(Metric):
    """
    Counter metric that only goes up.

    Usage:
        counter = Counter("requests_total", "Total requests")
        counter.inc()
        counter.inc(5)
        counter.inc(tags={"method": "GET"})
    """

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment counter."""
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._values[key] += value

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


class Gauge(Metric):
    """
    Gauge metric that can go up and down.

    Usage:
        gauge = Gauge("active_connections", "Active connections")
        gauge.set(10)
        gauge.inc()
        gauge.dec()
    """

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, description)
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def set(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._values[key] += value

    def dec(self, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._values[key] -= value

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


class Histogram(Metric):
    """
    Histogram for measuring distributions.

    Usage:
        histogram = Histogram("request_duration", buckets=[0.1, 0.5, 1.0])
        histogram.observe(0.3)
    """

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
    ):
        super().__init__(name, description)
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[tuple, Dict[float, int]] = defaultdict(lambda: {b: 0 for b in self._buckets})
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._totals: Dict[tuple, int] = defaultdict(int)
        self._lock = Lock()

    def observe(self, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((tags or {}).items()))
        with self._lock:
            self._sums[key] += value
            self._totals[key] += 1
            for bucket in self._buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def collect(self) -> List[MetricValue]:
        values = []
        with self._lock:
            for key in self._totals:
                tags = dict(key)
                # Sum
                values.append(
                    MetricValue(
                        name=f"{self._name}_sum",
                        value=self._sums[key],
                        tags=tags,
                    )
                )
                # Count
                values.append(
                    MetricValue(
                        name=f"{self._name}_count",
                        value=self._totals[key],
                        tags=tags,
                    )
                )
                # Buckets
                for bucket in self._buckets:
                    values.append(
                        MetricValue(
                            name=f"{self._name}_bucket",
                            value=self._counts[key][bucket],
                            tags={**tags, "le": str(bucket)},
                        )
                    )
        return values


class Timer:
    """
    Context manager for timing operations.

    Usage:
        with Timer(histogram):
            do_work()

        # Or as decorator
        @timer(histogram)
        def do_work():
            ...
    """

    def __init__(self, histogram: Histogram, tags: Optional[Dict[str, str]] = None):
        self._histogram = histogram
        self._tags = tags
        self._start: Optional[float] = None

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        if self._start:
            duration = time.perf_counter() - self._start
            self._histogram.observe(duration, self._tags)


def timer(histogram: Histogram, tags: Optional[Dict[str, str]] = None):
    """Decorator for timing functions."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            with Timer(histogram, tags):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class MetricsCollector:
    """
    Central collector for all metrics.

    Usage:
        collector = MetricsCollector()

        requests = collector.counter("requests_total")
        active = collector.gauge("active_connections")
        duration = collector.histogram("request_duration")

        # Collect all metrics
        all_values = collector.collect_all()
    """

    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = Lock()

    def counter(self, name: str, description: str = "") -> Counter:
        """Get or create counter."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, description)
            return self._metrics[name]  # type: ignore

    def gauge(self, name: str, description: str = "") -> Gauge:
        """Get or create gauge."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, description)
            return self._metrics[name]  # type: ignore

    def histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[tuple] = None,
    ) -> Histogram:
        """Get or create histogram."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, description, buckets)
            return self._metrics[name]  # type: ignore

    def collect_all(self) -> List[MetricValue]:
        """Collect all metric values."""
        values = []
        with self._lock:
            for metric in self._metrics.values():
                values.extend(metric.collect())
        return values

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary."""
        result = {}
        for value in self.collect_all():
            key = value.name
            if value.tags:
                key += "{" + ",".join(f'{k}="{v}"' for k, v in value.tags.items()) + "}"
            result[key] = value.value
        return result


# Global instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


__all__ = [
    "Metric",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "timer",
    "MetricsCollector",
    "MetricValue",
    "get_metrics",
]
