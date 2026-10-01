from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.roadster_ephemeris import RoadsterEphemeris
from nightazimuth.star_field import DeepSkyPoint, PlanetPoint, StarFieldSnapshot, StarPoint


def _roadster() -> RoadsterEphemeris:
    return RoadsterEphemeris(
        id="tesla-roadster-starman",
        name="Tesla Roadster / Starman",
        object_type="Heliocentric artificial object",
        international_designator="2018-017A",
        jpl_target_id="-143205",
        launch_date="2018-02-06",
        launch_vehicle="Falcon Heavy demo mission",
        payload="2008 Tesla Roadster with Starman mannequin",
        body_colour="Red",
        tracking_mode="Predicted ephemeris (not live telemetry)",
        data_source="NASA/JPL Horizons",
        ephemeris_at="2099-01-01T00:00:00+00:00",
        azimuth_deg=123.4,
        elevation_deg=25.6,
        right_ascension_deg=12.3,
        declination_deg=-4.5,
        apparent_magnitude=None,
        distance_earth_au=2.0,
        distance_earth_km=299_195_741.4,
        distance_sun_au=1.5,
        earth_range_rate_km_s=3.2,
        heliocentric_speed_km_s=28.0,
        observer_relative_speed_km_s=22.0,
        light_time_minutes=16.6,
        solar_elongation_deg=90.0,
        phase_angle_deg=40.0,
        heliocentric_ecliptic_longitude_deg=33.0,
        heliocentric_ecliptic_latitude_deg=-2.0,
        constellation="Vir",
    )


def test_sky_endpoint_contract(monkeypatch):
    snapshot = StarFieldSnapshot(
        stars=(StarPoint(1, 10.0, 20.0, 1.0, "Test Star"),),
        planets=(PlanetPoint("Mars", 30.0, 40.0),),
        constellation_lines=(),
        calculated_at=datetime(2099, 1, 1, tzinfo=UTC),
        galaxies=(DeepSkyPoint("Test Galaxy", 50.0, 60.0),),
    )
    seen_cache_directories: list[Path] = []

    class FakeEngine:
        def __init__(self, observer, cache_directory):
            seen_cache_directories.append(Path(cache_directory))

        def snapshot(self):
            return snapshot

    monkeypatch.setattr("nightazimuth.api_sky.StarFieldEngine", FakeEngine)
    monkeypatch.setattr(
        "nightazimuth.api_sky._ROADSTER_PROVIDER.lookup",
        lambda observer, when=None: _roadster(),
    )
    response = TestClient(app).get("/api/v1/sky?latitude=55&longitude=-4")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stars"][0]["name"] == "Test Star"
    assert payload["planets"][0]["name"] == "Mars"
    assert payload["galaxies"][0]["name"] == "Test Galaxy"
    assert payload["deep_space_objects"][0]["name"] == "Tesla Roadster / Starman"
    assert payload["deep_space_objects"][0]["jpl_target_id"] == "-143205"
    assert seen_cache_directories == [Path("data/cache/api/skyfield")]

    timing = response.headers["Server-Timing"]
    assert "engine_init;dur=" in timing
    assert "snapshot;dur=" in timing
    assert "roadster;dur=" in timing
    assert "serialize;dur=" in timing
    assert "total;dur=" in timing
