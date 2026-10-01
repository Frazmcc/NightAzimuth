from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Any


_KNOWN_PREFIXES = (
    "/api/v1/aircraft",
    "/api/v1/airports",
    "/api/v1/geojson",
    "/api/v1/health",
    "/api/v1/observability",
    "/api/v1/observing",
    "/api/v1/satellites",
    "/api/v1/sky",
    "/api/v1/weather",
)


@dataclass(frozen=True, slots=True)
class RequestSample:
    timestamp: float
    path: str
    status_code: int
    duration_ms: float


def _normalise_path(path: str) -> str:
    for prefix in _KNOWN_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix
    if path.startswith("/api/"):
        return "/api/other"
    return "/other"


class ObservabilityStore:
    def __init__(self, *, max_latency_samples: int = 600) -> None:
        self._lock = Lock()
        self._started_at = monotonic()
        self._latency_samples: deque[RequestSample] = deque(maxlen=max_latency_samples)
        self._request_buckets: dict[int, dict[str, list[int]]] = {}

    def record_request(self, *, path: str, status_code: int, duration_ms: float) -> None:
        path = _normalise_path(path)
        if path == "/api/v1/observability":
            return
        now = monotonic()
        second = int(now)
        is_error = status_code >= 400
        with self._lock:
            self._latency_samples.append(RequestSample(now, path, status_code, duration_ms))
            bucket = self._request_buckets.setdefault(second, {})
            counters = bucket.setdefault(path, [0, 0])
            counters[0] += 1
            counters[1] += int(is_error)
            cutoff = second - 300
            for old_second in [value for value in self._request_buckets if value < cutoff]:
                self._request_buckets.pop(old_second, None)

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        index = max(0, min(len(values) - 1, int(round((len(values) - 1) * percentile))))
        return values[index]

    def snapshot(self) -> dict[str, Any]:
        now = monotonic()
        now_second = int(now)
        with self._lock:
            samples = list(self._latency_samples)
            buckets = {
                second: {path: list(counts) for path, counts in paths.items()}
                for second, paths in self._request_buckets.items()
                if now_second - second <= 300
            }

        one_minute_total = 0
        five_minute_total = 0
        five_minute_errors = 0
        endpoint_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for second, paths in buckets.items():
            within_minute = now_second - second <= 60
            for path, (count, errors) in paths.items():
                five_minute_total += count
                five_minute_errors += errors
                endpoint_counts[path][0] += count
                endpoint_counts[path][1] += errors
                if within_minute:
                    one_minute_total += count

        recent_samples = [sample for sample in samples if now - sample.timestamp <= 300.0]
        latencies = [sample.duration_ms for sample in recent_samples]
        samples_by_path: dict[str, list[float]] = defaultdict(list)
        for sample in recent_samples:
            samples_by_path[sample.path].append(sample.duration_ms)

        endpoints = []
        for path, (count, errors) in endpoint_counts.items():
            durations = samples_by_path.get(path, [])
            endpoints.append({
                "path": path,
                "requests": count,
                "p95_ms": round(self._percentile(durations, 0.95), 1),
                "error_rate": round((errors / count) * 100.0, 2) if count else 0.0,
            })
        endpoints.sort(key=lambda item: item["requests"], reverse=True)

        successes = five_minute_total - five_minute_errors
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "process_uptime_seconds": round(now - self._started_at, 1),
            "api": {
                "requests_last_minute": one_minute_total,
                "requests_last_5_minutes": five_minute_total,
                "success_rate": round((successes / five_minute_total) * 100.0, 2) if five_minute_total else 100.0,
                "error_rate": round((five_minute_errors / five_minute_total) * 100.0, 2) if five_minute_total else 0.0,
                "p50_ms": round(self._percentile(latencies, 0.50), 1),
                "p95_ms": round(self._percentile(latencies, 0.95), 1),
                "latency_sample_count": len(recent_samples),
                "latency_samples_truncated": five_minute_total > len(recent_samples),
                "top_endpoints": endpoints[:8],
            },
        }


OBSERVABILITY = ObservabilityStore()
