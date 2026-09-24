from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.observing_planner import ViewingGuidance
from nightazimuth.weather import WeatherProviderError, WeatherSnapshot


def _snapshot() -> WeatherSnapshot:
    moment = datetime(2099, 1, 1, tzinfo=UTC)
    return WeatherSnapshot(
        source_name="synthetic",
        fetched_at_utc=moment,
        source_updated_at_utc=moment,
        points=(),
        from_cache=False,
        fallback_used=False,
    )


def test_observing_requires_coordinates() -> None:
    assert TestClient(app).get("/api/v1/observing").status_code == 422


def test_observing_validates_hours() -> None:
    response = TestClient(app).get(
        "/api/v1/observing?latitude=55.86&longitude=-4.25&hours=0"
    )
    assert response.status_code == 422


def test_observing_response_contract(monkeypatch) -> None:
    snapshot = _snapshot()
    guidance = ViewingGuidance(
        time_utc=snapshot.fetched_at_utc,
        rating="Very good",
        confidence="High",
        sun_altitude_deg=-25.0,
        cloud_percent=5.0,
        fog_percent=0.0,
        precipitation_mm=0.0,
        reasons=("astronomically dark", "5% forecast cloud"),
    )

    class FakeProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, observer):
            return snapshot

    class FakePlanner:
        def __init__(self, observer, **_kwargs) -> None:
            assert observer.latitude == 55.86

        def build(self, weather, *, hours):
            assert weather is snapshot
            assert hours == 24
            return (guidance,)

    monkeypatch.setattr("nightazimuth.api_observing.MetNorwayWeatherProvider", FakeProvider)
    monkeypatch.setattr("nightazimuth.api_observing.ObservingPlanner", FakePlanner)

    response = TestClient(app).get(
        "/api/v1/observing?latitude=55.86&longitude=-4.25"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["weather_source"] == "synthetic"
    assert payload["count"] == 1
    assert payload["guidance"][0]["rating"] == "Very good"
    assert payload["guidance"][0]["confidence"] == "High"
    assert payload["guidance"][0]["reasons"][0] == "astronomically dark"


def test_observing_provider_failure_returns_generic_503(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, observer):
            raise WeatherProviderError("private cache detail")

    monkeypatch.setattr("nightazimuth.api_observing.MetNorwayWeatherProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/observing?latitude=55.86&longitude=-4.25"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Observing guidance is temporarily unavailable"
