from __future__ import annotations

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.api_satellites import satellites
from nightazimuth.celestrak import CelestrakClient, CelestrakError
from nightazimuth.tracker import SatellitePosition


def test_satellite_endpoint_requires_observer_coordinates() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/satellites")

    assert response.status_code == 422


def test_satellite_endpoint_validates_coordinates() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/satellites?latitude=91&longitude=0")

    assert response.status_code == 422


def test_satellite_response_contract(monkeypatch) -> None:
    requested_groups: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group(self, group: str):
            requested_groups.append(group)
            return [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]

    class FakeTracker:
        def __init__(self, observer) -> None:
            assert observer.latitude == 55.86
            assert observer.longitude == -4.25

        def positions_above_horizon(self, elements, *, minimum_elevation_deg, at):
            elements = list(elements)
            assert len(elements) == 1
            assert elements[0]["OBJECT_NAME"] == "TEST SAT"
            assert set(elements[0]["_nightazimuth_groups"]) == {
                "VISUAL",
                "LAST-30-DAYS",
                "STATIONS",
            }
            assert minimum_elevation_deg == 10.0
            assert at.tzinfo is not None
            return [
                SatellitePosition(
                    name="TEST SAT",
                    norad_id="12345",
                    azimuth_deg=180.0,
                    elevation_deg=45.0,
                    range_km=500.0,
                )
            ]

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)

    payload = satellites(
        latitude=55.86,
        longitude=-4.25,
        altitude_m=50.0,
        minimum_elevation_deg=10.0,
        group="VISUAL",
        identification_detail=True,
    )

    assert set(requested_groups) == {"VISUAL", "LAST-30-DAYS", "STATIONS"}
    assert payload["source"] == "CelesTrak orbital data"
    assert payload["group"] == "VISUAL"
    assert payload["groups"] == ["VISUAL", "LAST-30-DAYS", "STATIONS"]
    assert payload["catalog_count"] == 1
    assert payload["count"] == 1
    assert payload["observer"] == {
        "latitude_deg": 55.86,
        "longitude_deg": -4.25,
        "altitude_m": 50.0,
    }
    assert payload["satellites"] == [
        {
            "name": "TEST SAT",
            "norad_id": "12345",
            "azimuth_deg": 180.0,
            "elevation_deg": 45.0,
            "range_km": 500.0,
            "object_id": None,
            "launch_id": None,
            "category": "Satellite",
            "source_groups": (),
            "epoch_utc": None,
            "inclination_deg": None,
            "period_minutes": None,
            "eccentricity": None,
            "track": (),
        }
    ]


def test_satellite_detail_can_be_disabled(monkeypatch) -> None:
    requested_groups: list[str] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group(self, group: str):
            requested_groups.append(group)
            return []

    class FakeTracker:
        def __init__(self, _observer) -> None:
            pass

        def positions_above_horizon(self, elements, *, minimum_elevation_deg, at):
            assert list(elements) == []
            return []

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)

    payload = satellites(
        latitude=55.86,
        longitude=-4.25,
        altitude_m=0.0,
        minimum_elevation_deg=0.0,
        group="VISUAL",
        identification_detail=False,
    )

    assert requested_groups == ["VISUAL"]
    assert payload["groups"] == ["VISUAL"]


def test_satellite_failure_does_not_expose_provider_detail(monkeypatch) -> None:
    def fail_load_group(self, group):
        raise CelestrakError("upstream secret-ish diagnostic / private cache path")

    monkeypatch.setattr(CelestrakClient, "load_group", fail_load_group)
    response = TestClient(app).get("/api/v1/satellites?latitude=55&longitude=-4")
    assert response.status_code == 503
    assert response.json() == {"detail": "Satellite data is temporarily unavailable"}
    assert "private cache" not in response.text
