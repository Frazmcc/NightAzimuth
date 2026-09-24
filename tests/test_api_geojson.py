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
    assert response.headers["content-type"].startswith("application/geo+json")
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"]["count"] == 1
    assert payload["metadata"]["source"]["fetched_at"] == snapshot.fetched_at.isoformat()
    assert payload["metadata"]["source"]["source_observed_at"] == snapshot.source_observed_at.isoformat()
    assert payload["metadata"]["source"]["coverage"] == "bounded observer area"
    feature = payload["features"][0]
    assert feature["type"] == "Feature"
    assert feature["id"] == "abc123"
    assert feature["geometry"]["type"] == "Point"
    longitude, latitude = feature["geometry"]["coordinates"]
    assert longitude == pytest.approx(-4.20, abs=1e-6)
    assert latitude == pytest.approx(55.90, abs=1e-5)
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


def test_aircraft_geojson_malformed_provider_payload_is_generic_503(monkeypatch) -> None:
    class BrokenProvider:
        def fetch_snapshot(self, observer, radius_km):
            raise OverflowError("timestamp out of range")

    monkeypatch.setattr("nightazimuth.api_geojson.AdsbLolProvider", BrokenProvider)

    response = TestClient(app).get(
        "/api/v1/geojson/aircraft?latitude=55.86&longitude=-4.25"
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Aircraft overlay is temporarily unavailable"


@pytest.mark.parametrize(
    "query",
    [
        "latitude=nan&longitude=-4.25",
        "latitude=55.86&longitude=nan",
        "latitude=55.86&longitude=-4.25&altitude_m=nan",
        "latitude=55.86&longitude=-4.25&radius_km=nan",
    ],
)
def test_aircraft_geojson_rejects_non_finite_query_values(query: str) -> None:
    response = TestClient(app).get(f"/api/v1/geojson/aircraft?{query}")
    assert response.status_code == 422
