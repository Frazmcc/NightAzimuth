from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.star_field import DeepSkyPoint, PlanetPoint, StarFieldSnapshot, StarPoint


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
    response = TestClient(app).get("/api/v1/sky?latitude=55&longitude=-4")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stars"][0]["name"] == "Test Star"
    assert payload["planets"][0]["name"] == "Mars"
    assert payload["galaxies"][0]["name"] == "Test Galaxy"
    assert seen_cache_directories == [Path("data/cache/api/skyfield")]
