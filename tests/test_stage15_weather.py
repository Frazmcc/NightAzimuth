from datetime import datetime, timezone

from nightazimuth.config import ObserverConfig
from nightazimuth.weather import MetNorwayWeatherProvider, parse_met_no_locationforecast


def _payload() -> dict:
    return {
        "properties": {
            "meta": {"updated_at": "2026-09-13T18:00:00Z"},
            "timeseries": [
                {
                    "time": "2026-09-13T19:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": 11.4,
                                "relative_humidity": 83.0,
                                "cloud_area_fraction": 62.0,
                                "cloud_area_fraction_low": 18.0,
                                "cloud_area_fraction_medium": 12.0,
                                "cloud_area_fraction_high": 54.0,
                                "fog_area_fraction": 3.0,
                                "wind_speed": 4.2,
                                "wind_from_direction": 240.0,
                            }
                        },
                        "next_1_hours": {"details": {"precipitation_amount": 0.1}},
                    },
                },
                {
                    "time": "2026-09-13T20:00:00Z",
                    "data": {
                        "instant": {"details": {"cloud_area_fraction": 48.0}},
                        "next_1_hours": {"details": {"precipitation_amount": 0.0}},
                    },
                },
            ],
        }
    }


def test_parse_met_no_locationforecast() -> None:
    fetched = datetime(2026, 9, 13, 18, 5, tzinfo=timezone.utc)
    snapshot = parse_met_no_locationforecast(_payload(), fetched_at_utc=fetched)

    assert snapshot.source_name == "MET Norway Locationforecast 2.0"
    assert snapshot.source_updated_at_utc == datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
    assert len(snapshot.points) == 2

    first = snapshot.points[0]
    assert first.air_temperature_c == 11.4
    assert first.relative_humidity_percent == 83.0
    assert first.cloud_total_percent == 62.0
    assert first.cloud_low_percent == 18.0
    assert first.cloud_medium_percent == 12.0
    assert first.cloud_high_percent == 54.0
    assert first.fog_percent == 3.0
    assert first.wind_speed_m_s == 4.2
    assert first.wind_from_direction_deg == 240.0
    assert first.precipitation_next_hour_mm == 0.1


def test_weather_snapshot_current_and_next() -> None:
    snapshot = parse_met_no_locationforecast(
        _payload(),
        fetched_at_utc=datetime(2026, 9, 13, 18, 5, tzinfo=timezone.utc),
    )
    now = datetime(2026, 9, 13, 19, 10, tzinfo=timezone.utc)

    assert snapshot.current_or_next(now) == snapshot.points[1]
    assert snapshot.next_points(4, now) == (snapshot.points[1],)


def test_weather_cache_key_is_hashed(tmp_path) -> None:
    provider = MetNorwayWeatherProvider(cache_directory=tmp_path)
    observer = ObserverConfig(latitude=10.0, longitude=20.0, altitude_m=100.0)

    path = provider._cache_path(observer)

    assert path.parent == tmp_path / "weather"
    assert path.name.startswith("met_no_")
    assert "10.0" not in path.name
    assert "20.0" not in path.name
