from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nightazimuth.aircraft import (
    AircraftObservation,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
)
from nightazimuth.api import app


def test_aircraft_endpoint_requires_observer_coordinates() -> None:
    response = TestClient(app).get("/api/v1/aircraft")
    assert response.status_code == 422


def test_aircraft_endpoint_validates_radius() -> None:
    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=0"
    )
    assert response.status_code == 422


def test_aircraft_response_contract(monkeypatch) -> None:
    now = datetime.now(UTC)
    observation = AircraftObservation(
        icao24="abc123",
        callsign="TEST1",
        latitude_deg=55.90,
        longitude_deg=-4.20,
        barometric_altitude_m=3000.0,
        geometric_altitude_m=3100.0,
        ground_speed_mps=120.0,
        track_deg=180.0,
        vertical_rate_mps=0.0,
        squawk="7000",
        on_ground=False,
        position_observed_at=now,
        contact_observed_at=now,
        source_id="adsb-lol",
        source_label="adsb.lol",
        source_kind=AircraftSourceKind.INTERNET,
    )
    snapshot = AircraftSnapshot(
        observations=(observation,),
        source_id="adsb-lol",
        source_label="adsb.lol",
        fetched_at=now,
        source_observed_at=now,
        coverage_description="bounded observer area",
        state=AircraftSnapshotState.LIVE,
    )

    class FakeProvider:
        def fetch_snapshot(self, observer, radius_km):
            assert observer.latitude_deg == 55.86
            assert observer.longitude_deg == -4.25
            assert radius_km == 100.0
            return snapshot

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["id"] == "adsb-lol"
    assert payload["source"]["state"] == "live"
    assert payload["count"] == 1
    assert payload["aircraft"][0]["icao24"] == "abc123"
    assert payload["aircraft"][0]["callsign"] == "TEST1"
    assert payload["aircraft"][0]["source_label"] == "adsb.lol"
    geojson = payload["geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    feature = geojson["features"][0]
    assert feature["id"] == "abc123"
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == pytest.approx([-4.20, 55.90], abs=1e-5)
    assert feature["properties"]["icao24"] == "abc123"
    assert feature["properties"]["callsign"] == "TEST1"
    assert feature["properties"]["track_deg"] == 180.0
    assert feature["properties"]["ground_speed_mps"] == 120.0
    assert feature["properties"]["vertical_rate_mps"] == 0.0
    assert feature["properties"]["position_age_seconds"] is not None
    assert feature["properties"]["source_id"] == "adsb-lol"
    assert feature["properties"]["source_label"] == "adsb.lol"
    assert geojson["metadata"]["source"]["id"] == "adsb-lol"
    assert geojson["metadata"]["count"] == 1


def test_aircraft_unavailable_returns_503(monkeypatch) -> None:
    now = datetime.now(UTC)
    snapshot = AircraftSnapshot(
        observations=(),
        source_id="adsb-lol",
        source_label="adsb.lol",
        fetched_at=now,
        source_observed_at=None,
        coverage_description="bounded observer area",
        state=AircraftSnapshotState.UNAVAILABLE,
        error="provider unavailable",
    )

    class FakeProvider:
        def fetch_snapshot(self, observer, radius_km):
            return snapshot

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "provider unavailable"
