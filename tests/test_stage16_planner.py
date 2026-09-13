from datetime import datetime, timedelta, timezone

from nightazimuth.observing_planner import ObservingPlanner
from nightazimuth.weather import WeatherPoint


def _point(*, cloud: float, rain: float = 0.0, fog: float = 0.0) -> WeatherPoint:
    return WeatherPoint(
        time_utc=datetime(2026, 9, 13, 22, 0, tzinfo=timezone.utc),
        air_temperature_c=10.0,
        relative_humidity_percent=80.0,
        cloud_total_percent=cloud,
        cloud_low_percent=cloud,
        cloud_medium_percent=0.0,
        cloud_high_percent=0.0,
        fog_percent=fog,
        wind_speed_m_s=2.0,
        wind_from_direction_deg=180.0,
        precipitation_next_hour_mm=rain,
    )


def _planner_with_sun_altitude(altitude: float) -> ObservingPlanner:
    planner = object.__new__(ObservingPlanner)
    planner._sun_altitude = lambda _moment: altitude
    return planner


def test_clear_dark_hour_is_very_good() -> None:
    planner = _planner_with_sun_altitude(-25.0)
    now = datetime(2026, 9, 13, 21, 0, tzinfo=timezone.utc)
    guidance = planner._guidance_for_point(_point(cloud=5.0), now)

    assert guidance.rating == "Very good"
    assert guidance.confidence == "High"
    assert "astronomically dark" in guidance.reasons


def test_cloud_and_rain_reduce_guidance() -> None:
    planner = _planner_with_sun_altitude(-25.0)
    now = datetime(2026, 9, 13, 21, 0, tzinfo=timezone.utc)
    guidance = planner._guidance_for_point(_point(cloud=95.0, rain=1.5, fog=30.0), now)

    assert guidance.rating == "Poor"
    assert any("forecast cloud" in reason for reason in guidance.reasons)
    assert any("precipitation" in reason for reason in guidance.reasons)


def test_daylight_is_not_rated_good_even_when_clear() -> None:
    planner = _planner_with_sun_altitude(15.0)
    now = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
    guidance = planner._guidance_for_point(_point(cloud=0.0), now)

    assert guidance.rating == "Poor"
    assert "daylight/sunset not complete" in guidance.reasons


def test_confidence_reduces_with_forecast_horizon() -> None:
    planner = _planner_with_sun_altitude(-25.0)
    point = _point(cloud=10.0)
    now = point.time_utc - timedelta(hours=20)
    guidance = planner._guidance_for_point(point, now)

    assert guidance.confidence == "Lower"
