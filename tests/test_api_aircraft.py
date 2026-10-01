from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
        last_timings = {
            "provider_request_ms": 11.0,
            "provider_decode_ms": 2.0,
            "provider_normalize_ms": 3.0,
            "provider_total_ms": 17.0,
        }

        def fetch_snapshot(self, observer, radius_km):
            assert observer.latitude_deg == 55.75
            assert observer.longitude_deg == -4.25
            assert radius_km == 463.0
            return snapshot

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 200
    timing = response.headers["Server-Timing"]
    for stage in (
        "provider_request",
        "provider_decode",
        "provider_normalize",
        "provider_total",
        "projection",
        "payload",
        "total",
    ):
        assert f"{stage};dur=" in timing
    assert "provider_request;dur=11.0" in timing
    assert "provider_decode;dur=2.0" in timing
    assert "provider_normalize;dur=3.0" in timing
    assert "provider_total;dur=17.0" in timing

    payload = response.json()
    assert payload["source"]["id"] == "adsb-lol"
    assert payload["source"]["state"] == "live"
    assert payload["source"]["provider_failover_used"] is False
    assert payload["source"]["regional_shared"] is True
    assert payload["source_observation_count"] == 1
    assert payload["fresh_contact_count"] == 1
    assert payload["maximum_position_age_seconds"] == 45.0
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
    # The API resolves a moving contact to request time, so a few metres of
    # dead-reckoning from the source fix are expected and are not contract drift.
    assert feature["geometry"]["coordinates"] == pytest.approx([-4.20, 55.90], abs=1e-4)
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


def test_recent_adsb_fix_is_not_dropped_after_prediction_window(monkeypatch) -> None:
    now = datetime.now(UTC)
    observation = AircraftObservation(
        icao24="abc124",
        callsign="RECENT1",
        latitude_deg=55.90,
        longitude_deg=-4.20,
        barometric_altitude_m=3000.0,
        geometric_altitude_m=3100.0,
        ground_speed_mps=120.0,
        track_deg=180.0,
        vertical_rate_mps=0.0,
        squawk="7000",
        on_ground=False,
        position_observed_at=now - timedelta(seconds=30),
        contact_observed_at=now - timedelta(seconds=2),
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
            return snapshot

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_observation_count"] == 1
    assert payload["count"] == 1
    assert payload["fresh_contact_count"] == 0
    assert payload["aircraft"][0]["icao24"] == "abc124"
    assert payload["aircraft"][0]["position_state"] == "stale"
    assert 29.0 <= payload["aircraft"][0]["position_age_seconds"] <= 31.0


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
        last_timings = {
            "provider_request_ms": 25.0,
            "provider_decode_ms": 0.0,
            "provider_normalize_ms": 0.0,
            "provider_total_ms": 25.0,
        }

        def fetch_snapshot(self, observer, radius_km):
            return snapshot

    class FakeSecondaryProvider(FakeProvider):
        provider_id = "airplanes-live"

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)
    monkeypatch.setattr("nightazimuth.api_aircraft.AirplanesLiveProvider", FakeSecondaryProvider)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Aircraft data is temporarily unavailable"
    timing = response.headers["Server-Timing"]
    assert "provider_request;dur=25.0" in timing
    assert "provider_total;dur=25.0" in timing
    assert "provider_failover_request;dur=25.0" in timing
    assert "total;dur=" in timing
