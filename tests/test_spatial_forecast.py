from datetime import datetime, timezone

from nightazimuth.spatial_forecast import nearest_forecast_point, render_spatial_forecast
from nightazimuth.weather import WeatherPoint, WeatherSnapshot


def _point(hour: int, cloud: float, rain: float) -> WeatherPoint:
    return WeatherPoint(
        time_utc=datetime(2026, 9, 13, hour, 0, tzinfo=timezone.utc),
        air_temperature_c=10.0,
        relative_humidity_percent=80.0,
        cloud_total_percent=cloud,
        cloud_low_percent=cloud,
        cloud_medium_percent=0.0,
        cloud_high_percent=0.0,
        fog_percent=0.0,
        wind_speed_m_s=2.0,
        wind_from_direction_deg=180.0,
        precipitation_next_hour_mm=rain,
    )


def test_nearest_forecast_point_chooses_closest_time() -> None:
    snapshot = WeatherSnapshot(
        source_name="synthetic",
        fetched_at_utc=datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc),
        source_updated_at_utc=None,
        points=(_point(20, 20.0, 0.0), _point(21, 80.0, 1.0)),
    )
    target = datetime(2026, 9, 13, 20, 40, tzinfo=timezone.utc)
    assert nearest_forecast_point(snapshot, target).time_utc.hour == 21


def test_render_spatial_forecast_returns_translucent_overlay() -> None:
    cloud = (
        (0.0, 50.0, 100.0),
        (25.0, 75.0, 100.0),
        (0.0, 25.0, 50.0),
    )
    rain = (
        (0.0, 0.0, 0.0),
        (0.0, 0.5, 1.0),
        (0.0, 0.0, 0.0),
    )
    image = render_spatial_forecast(cloud, rain, width=64, height=64)
    assert image.mode == "RGBA"
    assert image.size == (64, 64)
    assert image.getchannel("A").getextrema()[1] > 0
