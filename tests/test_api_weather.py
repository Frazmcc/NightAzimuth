from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.weather import WeatherPoint, WeatherProviderError, WeatherSnapshot


def _point() -> WeatherPoint:
    return WeatherPoint(
        time_utc=datetime.now(UTC) + timedelta(hours=1),
        air_temperature_c=12.5,
        relative_humidity_percent=80.0,
        cloud_total_percent=40.0,
        cloud_low_percent=20.0,
        cloud_medium_percent=10.0,
        cloud_high_percent=10.0,
        fog_percent=0.0,
        wind_speed_m_s=4.0,
        wind_from_direction_deg=220.0,
        precipitation_next_hour_mm=0.2,
    )


def test_weather_endpoint_requires_observer_coordinates() -> None:
    assert TestClient(app).get("/api/v1/weather").status_code == 422


def test_weather_endpoint_validates_forecast_count() -> None:
    response = TestClient(app).get(
        "/api/v1/weather?latitude=55.86&longitude=-4.25&forecast_points=0"
    )
    assert response.status_code == 422


def test_weather_response_contract(monkeypatch) -> None:
    point = _point()
    snapshot = WeatherSnapshot(
        source_name="MET Norway Locationforecast 2.0",
        fetched_at_utc=point.time_utc,
        source_updated_at_utc=point.time_utc,
        points=(point,),
        from_cache=True,
    )

    class FakeProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, observer):
            assert observer.latitude == 55.86
            assert observer.longitude == -4.25
            return snapshot

    monkeypatch.setattr("nightazimuth.api_weather.MetNorwayWeatherProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/weather?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "MET Norway Locationforecast 2.0"
    assert payload["from_cache"] is True
    assert payload["current"]["air_temperature_c"] == 12.5
    assert len(payload["forecast"]) == 1


def test_weather_unavailable_returns_503(monkeypatch) -> None:
    class FakeProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, observer):
            raise WeatherProviderError("weather unavailable")

    monkeypatch.setattr("nightazimuth.api_weather.MetNorwayWeatherProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/weather?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "weather unavailable"
