from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.observability import ObservabilityStore


def test_observability_store_summarises_requests_without_query_data() -> None:
    store = ObservabilityStore(max_requests=10)
    store.record_request(path="/api/v1/aircraft", status_code=200, duration_ms=40.0)
    store.record_request(path="/api/v1/aircraft", status_code=503, duration_ms=120.0)
    store.record_request(path="/api/v1/weather", status_code=200, duration_ms=20.0)

    payload = store.snapshot()

    assert payload["api"]["requests_last_5_minutes"] == 3
    assert payload["api"]["error_rate"] > 0
    assert payload["api"]["p95_ms"] >= 40.0
    assert payload["api"]["top_endpoints"][0]["path"] == "/api/v1/aircraft"
    assert "?" not in payload["api"]["top_endpoints"][0]["path"]


def test_observability_store_tracks_aircraft_source_state() -> None:
    store = ObservabilityStore()
    store.record_aircraft(
        source_id="adsb-lol",
        source_label="adsb.lol",
        source_state="fresh",
        source_observation_count=120,
        returned_count=14,
        fresh_contact_count=13,
        cache_hit=True,
        fallback_used=False,
        provider_failover_used=False,
    )

    aircraft = store.snapshot()["aircraft"]
    assert aircraft["source_id"] == "adsb-lol"
    assert aircraft["source_observation_count"] == 120
    assert aircraft["cache_hit"] is True
    assert aircraft["last_success_at"] is not None


def test_observability_endpoint_is_public_read_only_telemetry() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "application_version" in payload
    assert "process_uptime_seconds" in payload
    assert "api" in payload
    assert "aircraft" in payload
