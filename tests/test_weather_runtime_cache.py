from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from nightazimuth import api_observing, api_weather
from nightazimuth.api import app
from nightazimuth.observing_planner import ViewingGuidance
from nightazimuth.weather import WeatherPoint, WeatherSnapshot
from nightazimuth.weather_snapshot_cache import API_WEATHER_SNAPSHOT_CACHE


def _snapshot() -> WeatherSnapshot:
    now = datetime.now(UTC)
    point = WeatherPoint(
        time_utc=now + timedelta(hours=1),
        air_temperature_c=10.0,
        relative_humidity_percent=80.0,
        cloud_total_percent=20.0,
        cloud_low_percent=10.0,
        cloud_medium_percent=5.0,
        cloud_high_percent=5.0,
        fog_percent=0.0,
        wind_speed_m_s=2.0,
        wind_from_direction_deg=180.0,
        precipitation_next_hour_mm=0.0,
    )
    return WeatherSnapshot(
        source_name="synthetic",
        fetched_at_utc=now,
        source_updated_at_utc=now,
        points=(point,),
    )


def test_weather_and_observing_share_one_runtime_snapshot(monkeypatch) -> None:
    API_WEATHER_SNAPSHOT_CACHE.clear()
    snapshot = _snapshot()
    calls = 0

    class FakeProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, _observer):
            nonlocal calls
            calls += 1
            return snapshot

    class FakePlanner:
        def __init__(self, _observer, **_kwargs) -> None:
            pass

        def build(self, weather, *, hours):
            assert weather is snapshot
            assert hours == 24
            point = snapshot.points[0]
            return (
                ViewingGuidance(
                    time_utc=point.time_utc,
                    rating="Good",
                    confidence="High",
                    sun_altitude_deg=-20.0,
                    cloud_percent=20.0,
                    fog_percent=0.0,
                    precipitation_mm=0.0,
                    reasons=("astronomically dark",),
                ),
            )

    monkeypatch.setattr(api_weather, "MetNorwayWeatherProvider", FakeProvider)
    monkeypatch.setattr(api_observing, "MetNorwayWeatherProvider", FakeProvider)
    monkeypatch.setattr(api_observing, "ObservingPlanner", FakePlanner)

    client = TestClient(app)
    weather_response = client.get("/api/v1/weather?latitude=55.86&longitude=-4.25")
    observing_response = client.get("/api/v1/observing?latitude=55.86&longitude=-4.25")
    API_WEATHER_SNAPSHOT_CACHE.clear()

    assert weather_response.status_code == 200
    assert observing_response.status_code == 200
    assert calls == 1
    assert "weather_load;dur=" in weather_response.headers["Server-Timing"]
    assert "weather_load;dur=0.0" in observing_response.headers["Server-Timing"]
    assert "planner_build;dur=" in observing_response.headers["Server-Timing"]
