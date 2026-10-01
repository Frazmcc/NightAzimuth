from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from time import monotonic
from typing import Any


@dataclass(frozen=True, slots=True)
class RequestSample:
    timestamp: float
    path: str
    status_code: int
    duration_ms: float


class ObservabilityStore:
    def __init__(self, *, max_requests: int = 600) -> None:
        self._lock = Lock()
        self._started_at = monotonic()
        self._requests: deque[RequestSample] = deque(maxlen=max_requests)
        self._aircraft: dict[str, Any] = {
            "source_id": None,
            "source_label": None,
            "source_state": None,
            "source_observed_at": None,
            "last_success_at": None,
            "last_request_at": None,
            "source_observation_count": 0,
            "returned_count": 0,
            "fresh_contact_count": 0,
            "cache_hit": False,
            "fallback_used": False,
            "provider_failover_used": False,
            "provider_request_ms": 0.0,
            "provider_total_ms": 0.0,
            "provider_retry_count": 0.0,
            "provider_failover_request_ms": 0.0,
            "provider_failover_total_ms": 0.0,
            "error": None,
        }

    def record_request(self, *, path: str, status_code: int, duration_ms: float) -> None:
        if path == "/api/v1/observability":
            return
        with self._lock:
            self._requests.append(RequestSample(monotonic(), path, status_code, duration_ms))

    def record_aircraft(self, **values: Any) -> None:
        with self._lock:
            self._aircraft.update(values)
            self._aircraft["last_request_at"] = datetime.now(UTC).isoformat()
            if values.get("error") is None and values.get("source_state") != "unavailable":
                self._aircraft["last_success_at"] = datetime.now(UTC).isoformat()

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        index = max(0, min(len(values) - 1, int(round((len(values) - 1) * percentile))))
        return values[index]

    def snapshot(self) -> dict[str, Any]:
        now = monotonic()
        with self._lock:
            requests = list(self._requests)
            aircraft = dict(self._aircraft)

        recent = [sample for sample in requests if now - sample.timestamp <= 300.0]
        one_minute = [sample for sample in requests if now - sample.timestamp <= 60.0]
        successful = [sample for sample in recent if sample.status_code < 500]
        failures = [sample for sample in recent if sample.status_code >= 500]
        latencies = [sample.duration_ms for sample in recent]

        endpoint_groups: dict[str, list[RequestSample]] = defaultdict(list)
        for sample in recent:
            endpoint_groups[sample.path].append(sample)
        endpoints = []
        for path, samples in endpoint_groups.items():
            durations = [sample.duration_ms for sample in samples]
            errors = sum(sample.status_code >= 500 for sample in samples)
            endpoints.append({
                "path": path,
                "requests": len(samples),
                "p95_ms": round(self._percentile(durations, 0.95), 1),
                "error_rate": round((errors / len(samples)) * 100.0, 2),
            })
        endpoints.sort(key=lambda item: item["requests"], reverse=True)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "process_uptime_seconds": round(now - self._started_at, 1),
            "api": {
                "requests_last_minute": len(one_minute),
                "requests_last_5_minutes": len(recent),
                "success_rate": round((len(successful) / len(recent)) * 100.0, 2) if recent else 100.0,
                "error_rate": round((len(failures) / len(recent)) * 100.0, 2) if recent else 0.0,
                "p50_ms": round(self._percentile(latencies, 0.50), 1),
                "p95_ms": round(self._percentile(latencies, 0.95), 1),
                "top_endpoints": endpoints[:8],
            },
            "aircraft": aircraft,
        }


OBSERVABILITY = ObservabilityStore()
