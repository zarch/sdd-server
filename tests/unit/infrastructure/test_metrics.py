"""Tests for metrics collection."""

from __future__ import annotations

import threading
import time

import pytest

from sdd_server.infrastructure.observability.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    Timer,
    get_metrics,
    metric_counter,
    metric_timer,
)


class TestCounter:
    """Tests for Counter metric."""

    def test_initial_value(self) -> None:
        counter = Counter(name="test_counter")
        assert counter.value == 0.0

    def test_increment(self) -> None:
        counter = Counter(name="test_counter")
        counter.increment()
        assert counter.value == 1.0

    def test_increment_by_amount(self) -> None:
        counter = Counter(name="test_counter")
        counter.increment(5.0)
        assert counter.value == 5.0

    def test_multiple_increments(self) -> None:
        counter = Counter(name="test_counter")
        counter.increment()
        counter.increment()
        counter.increment(3.0)
        assert counter.value == 5.0

    def test_increment_negative_raises(self) -> None:
        counter = Counter(name="test_counter")
        with pytest.raises(ValueError, match="positive"):
            counter.increment(-1.0)

    def test_reset(self) -> None:
        counter = Counter(name="test_counter")
        counter.increment(10.0)
        counter.reset()
        assert counter.value == 0.0

    def test_thread_safety(self) -> None:
        counter = Counter(name="test_counter")
        threads = [threading.Thread(target=lambda: counter.increment(1.0)) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert counter.value == 100.0


class TestGauge:
    """Tests for Gauge metric."""

    def test_initial_value(self) -> None:
        gauge = Gauge(name="test_gauge")
        assert gauge.value == 0.0

    def test_set(self) -> None:
        gauge = Gauge(name="test_gauge")
        gauge.set(42.0)
        assert gauge.value == 42.0

    def test_increment(self) -> None:
        gauge = Gauge(name="test_gauge")
        gauge.set(10.0)
        gauge.increment(5.0)
        assert gauge.value == 15.0

    def test_decrement(self) -> None:
        gauge = Gauge(name="test_gauge")
        gauge.set(10.0)
        gauge.decrement(3.0)
        assert gauge.value == 7.0

    def test_can_go_negative(self) -> None:
        gauge = Gauge(name="test_gauge")
        gauge.set(5.0)
        gauge.decrement(10.0)
        assert gauge.value == -5.0

    def test_thread_safety(self) -> None:
        gauge = Gauge(name="test_gauge")
        gauge.set(0.0)

        def inc() -> None:
            for _ in range(100):
                gauge.increment(1.0)

        def dec() -> None:
            for _ in range(100):
                gauge.decrement(1.0)

        threads = [threading.Thread(target=inc) for _ in range(5)]
        threads += [threading.Thread(target=dec) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final value should be 0 (5*100 increments - 5*100 decrements)
        assert gauge.value == 0.0


class TestHistogram:
    """Tests for Histogram metric."""

    def test_empty_histogram(self) -> None:
        hist = Histogram(name="test_hist")
        assert hist.count == 0
        assert hist.sum == 0.0
        assert hist.get_percentile(50) is None

    def test_single_observation(self) -> None:
        hist = Histogram(name="test_hist")
        hist.observe(5.0)
        assert hist.count == 1
        assert hist.sum == 5.0
        assert hist.get_percentile(50) == 5.0

    def test_multiple_observations(self) -> None:
        hist = Histogram(name="test_hist")
        for i in range(1, 101):  # 1 to 100
            hist.observe(float(i))

        assert hist.count == 100
        assert hist.sum == 5050.0
        # Percentile uses integer index, so may be slightly off
        assert hist.get_percentile(50) == 50 or hist.get_percentile(50) == 51
        assert hist.get_percentile(95) == 95 or hist.get_percentile(95) == 96
        assert hist.get_percentile(99) == 99 or hist.get_percentile(99) == 100

    def test_bucket_counts(self) -> None:
        hist = Histogram(name="test_hist", buckets=(0.1, 0.5, 1.0, 5.0))
        hist.observe(0.05)
        hist.observe(0.2)
        hist.observe(0.3)
        hist.observe(2.0)
        hist.observe(10.0)

        buckets = hist.bucket_counts
        assert buckets[0.1] == 1  # 0.05 <= 0.1
        assert buckets[0.5] == 3  # 0.05, 0.2, 0.3 <= 0.5
        assert buckets[1.0] == 3  # same
        assert buckets[5.0] == 4  # + 2.0 <= 5.0


class TestTimer:
    """Tests for Timer metric."""

    def test_timer_context_manager(self) -> None:
        timer = Timer(name="test_timer")
        with timer:
            time.sleep(0.01)

        assert timer.elapsed >= 0.01
        assert not timer._running

    def test_timer_start_stop(self) -> None:
        timer = Timer(name="test_timer")
        timer.start()
        time.sleep(0.01)
        elapsed = timer.stop()

        assert elapsed >= 0.01
        assert timer.elapsed >= 0.01
        assert not timer._running

    def test_timer_without_start(self) -> None:
        timer = Timer(name="test_timer")
        elapsed = timer.stop()
        assert elapsed == 0.0

    def test_timer_elapsed_while_running(self) -> None:
        timer = Timer(name="test_timer")
        timer.start()
        time.sleep(0.01)
        elapsed_running = timer.elapsed
        timer.stop()

        assert elapsed_running >= 0.01


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_counter_creation(self) -> None:
        collector = MetricsCollector(prefix="test")
        counter = collector.counter("requests")
        counter.increment(5.0)
        assert counter.name == "test_requests"
        assert counter.value == 5.0

    def test_counter_reuse(self) -> None:
        collector = MetricsCollector(prefix="test")
        counter1 = collector.counter("requests")
        counter2 = collector.counter("requests")
        assert counter1 is counter2

    def test_gauge_creation(self) -> None:
        collector = MetricsCollector(prefix="test")
        gauge = collector.gauge("connections")
        gauge.set(42.0)
        assert gauge.name == "test_connections"
        assert gauge.value == 42.0

    def test_histogram_creation(self) -> None:
        collector = MetricsCollector(prefix="test")
        hist = collector.histogram("latency")
        hist.observe(0.1)
        assert hist.name == "test_latency"
        assert hist.count == 1

    def test_timer_creation(self) -> None:
        collector = MetricsCollector(prefix="test")
        timer = collector.timer("operation")
        assert timer.name == "test_operation"

    def test_get_all_metrics(self) -> None:
        collector = MetricsCollector(prefix="test")
        collector.counter("requests").increment(10.0)
        collector.gauge("connections").set(5.0)
        collector.histogram("latency").observe(0.1)

        metrics = collector.get_all_metrics()
        assert metrics["counters"]["test_requests"] == 10.0
        assert metrics["gauges"]["test_connections"] == 5.0
        assert metrics["histograms"]["test_latency"]["count"] == 1

    def test_prometheus_format(self) -> None:
        collector = MetricsCollector(prefix="test")
        collector.counter("requests").increment(10.0)
        collector.gauge("connections").set(5.0)

        output = collector.to_prometheus_format()
        assert "# TYPE test_requests counter" in output
        assert "test_requests 10.0" in output
        assert "# TYPE test_connections gauge" in output
        assert "test_connections 5.0" in output

    def test_reset(self) -> None:
        collector = MetricsCollector(prefix="test")
        collector.counter("requests").increment(10.0)
        collector.reset()
        assert len(collector._counters) == 0


class TestGlobalFunctions:
    """Tests for global metric functions."""

    def test_get_metrics_singleton(self) -> None:
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_metric_counter(self) -> None:
        counter = metric_counter("test_global_counter")
        assert counter.name == "sdd_test_global_counter"

    def test_metric_timer(self) -> None:
        timer = metric_timer("test_global_timer")
        assert timer.name == "sdd_test_global_timer"
