from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nightazimuth.aircraft import (
    AircraftObservation,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
)
from nightazimuth.api import app


def _snapshot(state: AircraftSnapshotState = AircraftSnapshotState.LIVE) -> AircraftSnapshot:
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
    return AircraftSnapshot(
        observations=(observation,) if state == AircraftSnapshotState.LIVE else (),
        source_id="adsb-lol",
        source_label="adsb.lol",
        fetched_at=now,
        source_observed_at=now if state == AircraftSnapshotState.LIVE else None,
        coverage_description="bounded observer area",
        state=state,
        error="provider unavailable" if state == AircraftSnapshotState.UNAVAILABLE else None,
    )


def test_aircraft_geojson_requires_coordinates() -> None:
    assert TestClient(app).get("/api/v1/geojson/aircraft").status_code == 422


def test_aircraft_geojson_contract(monkeypatch) -> None:
    snapshot = _snapshot()

    class FakeProvider:
        def fetch_snapshot(self, observer, radius_km):
            return snapshot

    monkeypatch.setattr("nightazimuth.api_geojson.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/geojson/aircraft?latitude=55.86&longitude=-4.25"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] == 1
    feature = payload["features"][0]
    assert feature["type"] == "Feature"
    assert feature["id"] == "abc123"
    assert feature["geometry"] == {
        "type": "Point",
        "coordinates": [-4.20, 55.90],
    }
    assert feature["properties"]["callsign"] == "TEST1"


def test_aircraft_geojson_unavailable_is_generic_503(monkeypatch) -> None:
    snapshot = _snapshot(AircraftSnapshotState.UNAVAILABLE)

    class FakeProvider:
        def fetch_snapshot(self, observer, radius_km):
            return snapshot

    monkeypatch.setattr("nightazimuth.api_geojson.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/geojson/aircraft?latitude=55.86&longitude=-4.25"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Aircraft overlay is temporarily unavailable"
