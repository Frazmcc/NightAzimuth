from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nightazimuth.aircraft import AircraftSnapshot, AircraftSnapshotState
from nightazimuth.api import app
from nightazimuth.api_aircraft import _AIRCRAFT_SNAPSHOT_CACHE, _provider_request_scope
from nightazimuth.aircraft import AircraftObserver


def test_live_sky_observers_in_same_region_share_one_provider_snapshot(monkeypatch):
    _AIRCRAFT_SNAPSHOT_CACHE.clear()
    calls = []
    now = datetime.now(UTC)

    class FakeProvider:
        last_timings = {"provider_request_ms": 1.0, "provider_total_ms": 1.0}

        def fetch_snapshot(self, observer, radius_km):
            calls.append((observer.latitude_deg, observer.longitude_deg, radius_km))
            return AircraftSnapshot(
                observations=(),
                source_id="adsb-lol",
                source_label="adsb.lol",
                fetched_at=now,
                source_observed_at=now,
                coverage_description="regional test snapshot",
                state=AircraftSnapshotState.LIVE,
            )

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)
    client = TestClient(app)

    first = client.get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=400&minimum_elevation_deg=-90"
    )
    second = client.get(
        "/api/v1/aircraft?latitude=55.92&longitude=-4.18&radius_km=200&minimum_elevation_deg=0"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 1
    assert calls[0] == (55.75, -4.25, 463.0)
    assert first.json()["source"]["regional_shared"] is True
    assert second.json()["source"]["regional_shared"] is True


def test_live_sky_observers_in_different_regions_do_not_share_provider_snapshot(monkeypatch):
    _AIRCRAFT_SNAPSHOT_CACHE.clear()
    calls = []
    now = datetime.now(UTC)

    class FakeProvider:
        last_timings = {"provider_request_ms": 1.0, "provider_total_ms": 1.0}

        def fetch_snapshot(self, observer, radius_km):
            calls.append((observer.latitude_deg, observer.longitude_deg, radius_km))
            return AircraftSnapshot(
                observations=(),
                source_id="adsb-lol",
                source_label="adsb.lol",
                fetched_at=now,
                source_observed_at=now,
                coverage_description="regional test snapshot",
                state=AircraftSnapshotState.LIVE,
            )

    monkeypatch.setattr("nightazimuth.api_aircraft.AdsbLolProvider", FakeProvider)
    client = TestClient(app)

    first = client.get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=400"
    )
    second = client.get(
        "/api/v1/aircraft?latitude=53.48&longitude=-2.24&radius_km=400"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 2


def test_requests_over_400_km_remain_observer_specific():
    observer = AircraftObserver(55.86, -4.25, 12.0)

    provider_observer, provider_radius, regional_shared = _provider_request_scope(
        observer,
        450.0,
    )

    assert provider_observer is observer
    assert provider_radius == 450.0
    assert regional_shared is False


def test_400_km_request_uses_small_cell_and_maximum_provider_radius():
    observer = AircraftObserver(55.86, -4.25, 12.0)

    provider_observer, provider_radius, regional_shared = _provider_request_scope(
        observer,
        400.0,
    )

    assert provider_observer.latitude_deg == 55.75
    assert provider_observer.longitude_deg == -4.25
    assert provider_observer.altitude_m == 0.0
    assert provider_radius == 463.0
    assert regional_shared is True
