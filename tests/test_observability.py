from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.observability import ObservabilityStore


def test_observability_store_summarises_requests_without_query_data() -> None:
    store = ObservabilityStore(max_latency_samples=10)
    store.record_request(path="/api/v1/aircraft", status_code=200, duration_ms=40.0)
    store.record_request(path="/api/v1/aircraft", status_code=503, duration_ms=120.0)
    store.record_request(path="/api/v1/weather", status_code=200, duration_ms=20.0)

    payload = store.snapshot()

    assert payload["api"]["requests_last_5_minutes"] == 3
    assert payload["api"]["error_rate"] > 0
    assert payload["api"]["p95_ms"] >= 40.0
    assert payload["api"]["top_endpoints"][0]["path"] == "/api/v1/aircraft"
    assert "?" not in payload["api"]["top_endpoints"][0]["path"]


def test_observability_counts_are_not_truncated_by_latency_sample_capacity() -> None:
    store = ObservabilityStore(max_latency_samples=2)
    for _ in range(7):
        store.record_request(path="/api/v1/sky", status_code=200, duration_ms=10.0)

    payload = store.snapshot()["api"]
    assert payload["requests_last_minute"] == 7
    assert payload["requests_last_5_minutes"] == 7
    assert payload["top_endpoints"][0]["requests"] == 7
    assert payload["latency_sample_count"] == 2
    assert payload["latency_samples_truncated"] is True


def test_observability_treats_4xx_as_errors() -> None:
    store = ObservabilityStore()
    store.record_request(path="/api/v1/sky", status_code=414, duration_ms=1.0)
    payload = store.snapshot()["api"]
    assert payload["success_rate"] == 0.0
    assert payload["error_rate"] == 100.0


def test_observability_normalises_unknown_paths_to_bound_cardinality() -> None:
    store = ObservabilityStore()
    for index in range(100):
        store.record_request(
            path=f"/api/v1/not-a-route-{index}",
            status_code=404,
            duration_ms=1.0,
        )

    endpoints = store.snapshot()["api"]["top_endpoints"]
    assert len(endpoints) == 1
    assert endpoints[0]["path"] == "/api/other"
    assert endpoints[0]["requests"] == 100


def test_observability_endpoint_is_public_read_only_telemetry() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "application_version" in payload
    assert "process_uptime_seconds" in payload
    assert "api" in payload
    assert "aircraft" not in payload
