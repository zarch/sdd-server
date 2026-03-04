"""Metrics collection for monitoring and observability.

Provides counters, gauges, histograms, and timers for tracking
application performance and behavior.
"""

from __future__ import annotations

import inspect
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

P = ParamSpec("P")
T = TypeVar("T")


class MetricType(Enum):
    """Type of metric being tracked."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Counter:
    """A monotonically increasing counter.

    Counters only go up (and reset to zero on restart).
    Use for tracking things like request counts, errors, events.
    """

    name: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    labels: dict[str, str] = field(default_factory=dict)

    def increment(self, amount: float = 1.0) -> None:
        """Increment the counter by the given amount."""
        if amount < 0:
            raise ValueError("Counter can only be incremented by positive values")
        with self._lock:
            self._value += amount

    def reset(self) -> None:
        """Reset counter to zero (typically called on restart)."""
        with self._lock:
            self._value = 0.0

    @property
    def value(self) -> float:
        """Get current counter value."""
        with self._lock:
            return self._value


@dataclass
class Gauge:
    """A value that can go up or down.

    Use for tracking things like current connections, memory usage,
    queue depth, temperature.
    """

    name: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    labels: dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        """Set the gauge to a specific value."""
        with self._lock:
            self._value = value

    def increment(self, amount: float = 1.0) -> None:
        """Increment the gauge by the given amount."""
        with self._lock:
            self._value += amount

    def decrement(self, amount: float = 1.0) -> None:
        """Decrement the gauge by the given amount."""
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        """Get current gauge value."""
        with self._lock:
            return self._value


@dataclass
class Histogram:
    """A distribution of values with configurable buckets.

    Use for tracking distributions like request latencies,
    response sizes, etc.
    """

    name: str
    buckets: Sequence[float] = field(
        default_factory=lambda: (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )
    _values: list[float] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    labels: dict[str, str] = field(default_factory=dict)
    _bucket_counts: dict[float, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Initialize bucket counts."""
        self._bucket_counts = {bucket: 0 for bucket in self.buckets}

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            self._values.append(value)
            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1

    @property
    def count(self) -> int:
        """Get total number of observations."""
        with self._lock:
            return len(self._values)

    @property
    def sum(self) -> float:
        """Get sum of all observations."""
        with self._lock:
            return sum(self._values)

    def get_percentile(self, percentile: float) -> float | None:
        """Get value at given percentile (0-100)."""
        with self._lock:
            if not self._values:
                return None
            sorted_values = sorted(self._values)
            index = int(len(sorted_values) * percentile / 100)
            return sorted_values[min(index, len(sorted_values) - 1)]

    @property
    def bucket_counts(self) -> dict[float, int]:
        """Get cumulative bucket counts."""
        with self._lock:
            return dict(self._bucket_counts)


@dataclass
class Timer:
    """A timer for measuring durations.

    Use for tracking operation latencies, processing times, etc.
    """

    name: str
    _start_time: float | None = field(default=None, repr=False)
    _elapsed: float = 0.0
    _running: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    labels: dict[str, str] = field(default_factory=dict)

    def start(self) -> Timer:
        """Start the timer."""
        with self._lock:
            self._start_time = time.perf_counter()
            self._running = True
        return self

    def stop(self) -> float:
        """Stop the timer and return elapsed seconds."""
        with self._lock:
            if not self._running or self._start_time is None:
                return 0.0
            self._elapsed = time.perf_counter() - self._start_time
            self._running = False
            return self._elapsed

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds (current if running, final if stopped)."""
        with self._lock:
            if self._running and self._start_time is not None:
                return time.perf_counter() - self._start_time
            return self._elapsed

    def __enter__(self) -> Timer:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.stop()


class MetricsCollector:
    """Central metrics collection and reporting.

    Collects all metrics and provides export functionality
    for monitoring systems like Prometheus.
    """

    def __init__(self, prefix: str = "sdd") -> None:
        """Initialize the metrics collector.

        Args:
            prefix: Prefix for all metric names (default: "sdd")
        """
        self.prefix = prefix
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, list[Timer]] = defaultdict(list)
        self._lock = threading.Lock()

    def _make_name(self, name: str) -> str:
        """Create full metric name with prefix."""
        return f"{self.prefix}_{name}"

    def counter(self, name: str, labels: dict[str, str] | None = None) -> Counter:
        """Get or create a counter.

        Args:
            name: Metric name (without prefix)
            labels: Optional labels for the metric

        Returns:
            Counter instance
        """
        full_name = self._make_name(name)
        with self._lock:
            if full_name not in self._counters:
                self._counters[full_name] = Counter(name=full_name, labels=labels or {})
            return self._counters[full_name]

    def gauge(self, name: str, labels: dict[str, str] | None = None) -> Gauge:
        """Get or create a gauge.

        Args:
            name: Metric name (without prefix)
            labels: Optional labels for the metric

        Returns:
            Gauge instance
        """
        full_name = self._make_name(name)
        with self._lock:
            if full_name not in self._gauges:
                self._gauges[full_name] = Gauge(name=full_name, labels=labels or {})
            return self._gauges[full_name]

    def histogram(
        self,
        name: str,
        buckets: Sequence[float] | None = None,
        labels: dict[str, str] | None = None,
    ) -> Histogram:
        """Get or create a histogram.

        Args:
            name: Metric name (without prefix)
            buckets: Optional bucket boundaries
            labels: Optional labels for the metric

        Returns:
            Histogram instance
        """
        full_name = self._make_name(name)
        with self._lock:
            if full_name not in self._histograms:
                self._histograms[full_name] = Histogram(
                    name=full_name,
                    buckets=buckets if buckets is not None else Histogram(name="_dummy_").buckets,
                    labels=labels or {},
                )
            return self._histograms[full_name]

    def timer(self, name: str, labels: dict[str, str] | None = None) -> Timer:
        """Create a new timer.

        Args:
            name: Metric name (without prefix)
            labels: Optional labels for the metric

        Returns:
            Timer instance
        """
        full_name = self._make_name(name)
        timer = Timer(name=full_name, labels=labels or {})
        with self._lock:
            self._timers[full_name].append(timer)
        return timer

    def record_timer(self, name: str, duration: float) -> None:
        """Record a timer observation directly.

        Args:
            name: Metric name (without prefix)
            duration: Duration in seconds
        """
        histogram = self.histogram(f"{name}_seconds")
        histogram.observe(duration)

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary with all metric values
        """
        with self._lock:
            return {
                "counters": {name: counter.value for name, counter in self._counters.items()},
                "gauges": {name: gauge.value for name, gauge in self._gauges.items()},
                "histograms": {
                    name: {
                        "count": hist.count,
                        "sum": hist.sum,
                        "buckets": hist.bucket_counts,
                        "p50": hist.get_percentile(50),
                        "p95": hist.get_percentile(95),
                        "p99": hist.get_percentile(99),
                    }
                    for name, hist in self._histograms.items()
                },
                "timers": {name: len(timers) for name, timers in self._timers.items()},
            }

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines: list[str] = []

        # Export counters
        for name, counter in sorted(self._counters.items()):
            lines.append(f"# TYPE {name} counter")
            label_str = self._format_labels(counter.labels)
            lines.append(f"{name}{label_str} {counter.value}")

        # Export gauges
        for name, gauge in sorted(self._gauges.items()):
            lines.append(f"# TYPE {name} gauge")
            label_str = self._format_labels(gauge.labels)
            lines.append(f"{name}{label_str} {gauge.value}")

        # Export histograms
        for name, hist in sorted(self._histograms.items()):
            lines.append(f"# TYPE {name} histogram")
            label_str = self._format_labels(hist.labels)

            # Bucket counts
            for bucket, count in sorted(hist.bucket_counts.items()):
                bucket_label = f'{{le="{bucket}"}}'
                if label_str:
                    bucket_label = f'{{{self._labels_to_str(hist.labels)}, le="{bucket}"}}'
                lines.append(f"{name}_bucket{bucket_label} {count}")

            # Sum and count
            lines.append(f"{name}_sum{label_str} {hist.sum}")
            lines.append(f"{name}_count{label_str} {hist.count}")

        return "\n".join(lines)

    @staticmethod
    def _format_labels(labels: dict[str, str]) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        return "{" + ", ".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"

    @staticmethod
    def _labels_to_str(labels: dict[str, str]) -> str:
        """Convert labels to string format."""
        return ", ".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    with _metrics_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
        return _metrics_collector


def metric_counter(name: str, labels: dict[str, str] | None = None) -> Counter:
    """Create or get a counter from the global collector.

    Args:
        name: Metric name (without prefix)
        labels: Optional labels

    Returns:
        Counter instance
    """
    return get_metrics().counter(name, labels)


def metric_timer(name: str, labels: dict[str, str] | None = None) -> Timer:
    """Create a timer from the global collector.

    Args:
        name: Metric name (without prefix)
        labels: Optional labels

    Returns:
        Timer instance
    """
    return get_metrics().timer(name, labels)


def timed(
    metric_name: str | None = None,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to time function execution.

    Args:
        metric_name: Optional metric name (defaults to function name)
        labels: Optional labels for the metric

    Returns:
        Decorated function
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        name = metric_name or func.__name__

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            with get_metrics().timer(name, labels) as timer:
                result = func(*args, **kwargs)
            get_metrics().record_timer(name, timer.elapsed)
            return result

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            timer = get_metrics().timer(name, labels)
            timer.start()
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
            finally:
                timer.stop()
                get_metrics().record_timer(name, timer.elapsed)
            return result  # type: ignore[no-any-return]

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator
