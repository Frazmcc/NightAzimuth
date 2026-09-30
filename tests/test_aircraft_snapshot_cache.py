from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread
from time import sleep

from fastapi.testclient import TestClient

from nightazimuth.aircraft import (
    AircraftObservation,
    AircraftObserver,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
)
from nightazimuth.aircraft_snapshot_cache import AircraftSnapshotCache, slice_snapshot_radius
from nightazimuth.api import app
from nightazimuth import api_aircraft


def _observation(icao24: str, latitude_deg: float, longitude_deg: float) -> AircraftObservation:
    now = datetime.now(UTC)
    return AircraftObservation(
        icao24=icao24,
        callsign=icao24.upper(),
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        barometric_altitude_m=9000.0,
        geometric_altitude_m=9100.0,
        ground_speed_mps=120.0,
        track_deg=90.0,
        vertical_rate_mps=0.0,
        squawk="7000",
        on_ground=False,
        position_observed_at=now,
        contact_observed_at=now,
        source_id="adsb-lol",
        source_label="adsb.lol",
        source_kind=AircraftSourceKind.INTERNET,
    )


def _snapshot(*observations: AircraftObservation) -> AircraftSnapshot:
    now = datetime.now(UTC)
    return AircraftSnapshot(
        observations=tuple(observations),
        source_id="adsb-lol",
        source_label="adsb.lol",
        fetched_at=now,
        source_observed_at=now,
        coverage_description="bounded observer area, 216 NM radius",
        state=AircraftSnapshotState.LIVE,
    )


def test_snapshot_cache_single_flights_concurrent_callers() -> None:
    cache = AircraftSnapshotCache(ttl_seconds=1.0, max_entries=2)
    snapshot = _snapshot(_observation("abc001", 0.1, 0.1))
    provider_started = Event()
    release_provider = Event()
    calls = 0
    results = []

    def fetcher():
        nonlocal calls
        calls += 1
        provider_started.set()
        assert release_provider.wait(timeout=2.0)
        return snapshot, {"provider_request_ms": 42.0}

    def worker() -> None:
        results.append(cache.get_or_fetch(("same",), fetcher))

    first = Thread(target=worker)
    first.start()
    assert provider_started.wait(timeout=1.0)

    second = Thread(target=worker)
    second.start()
    sleep(0.05)
    release_provider.set()

    first.join(timeout=2.0)
    second.join(timeout=2.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert calls == 1
    assert len(results) == 2
    assert sum(not result.cache_hit for result in results) == 1
    assert sum(result.cache_hit for result in results) == 1
    assert sum(bool(result.provider_timings) for result in results) == 1
    assert max(result.shared_wait_ms for result in results) > 0.0


def test_slice_snapshot_radius_preserves_requested_provider_boundary() -> None:
    observer = AircraftObserver(0.0, 0.0)
    near = _observation("abc002", 1.0, 0.0)
    far = _observation("abc003", 3.0, 0.0)

    sliced = slice_snapshot_radius(_snapshot(near, far), observer, 200.0)

    assert [observation.icao24 for observation in sliced.observations] == ["abc002"]
    assert sliced.coverage_description == "bounded observer area, 108 NM radius"


def test_live_sky_200_and_400_km_views_share_one_provider_snapshot(monkeypatch) -> None:
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()
    near = _observation("abc004", 1.0, 0.0)
    far = _observation("abc005", 3.0, 0.0)
    provider_snapshot = _snapshot(near, far)
    requested_radii: list[float] = []

    class FakeProvider:
        def __init__(self) -> None:
            self.last_timings = {
                "provider_request_ms": 25.0,
                "provider_decode_ms": 2.0,
                "provider_normalize_ms": 3.0,
                "provider_total_ms": 30.0,
            }

        def fetch_snapshot(self, observer, radius_km):
            requested_radii.append(radius_km)
            return provider_snapshot

    monkeypatch.setattr(api_aircraft, "AdsbLolProvider", FakeProvider)

    client = TestClient(app)
    radar = client.get(
        "/api/v1/aircraft?latitude=0&longitude=0&radius_km=400&minimum_elevation_deg=-90"
    )
    primary = client.get(
        "/api/v1/aircraft?latitude=0&longitude=0&radius_km=200&minimum_elevation_deg=-90"
    )
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()

    assert radar.status_code == 200
    assert primary.status_code == 200
    assert requested_radii == [400.0]
    assert radar.json()["source_observation_count"] == 2
    assert primary.json()["source_observation_count"] == 1
    assert primary.json()["source"]["coverage"] == "bounded observer area, 108 NM radius"
    assert "provider_request;dur=25.0" in radar.headers["Server-Timing"]
    assert "provider_request;dur=0.0" in primary.headers["Server-Timing"]
    assert "shared_wait;dur=" in primary.headers["Server-Timing"]
