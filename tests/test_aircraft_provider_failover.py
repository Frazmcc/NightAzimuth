from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nightazimuth.aircraft import AircraftSnapshot, AircraftSnapshotState
from nightazimuth.api import app
from nightazimuth import api_aircraft


def _snapshot(*, source_id: str, label: str, state: AircraftSnapshotState) -> AircraftSnapshot:
    now = datetime.now(UTC)
    return AircraftSnapshot(
        observations=(),
        source_id=source_id,
        source_label=label,
        fetched_at=now,
        source_observed_at=now if state != AircraftSnapshotState.UNAVAILABLE else None,
        coverage_description="provider failover test",
        state=state,
        error="temporary provider failure" if state == AircraftSnapshotState.UNAVAILABLE else None,
    )


def test_primary_success_does_not_call_secondary(monkeypatch):
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()
    secondary_calls = 0

    class Primary:
        last_timings = {"provider_request_ms": 10.0, "provider_total_ms": 12.0}

        def fetch_snapshot(self, observer, radius_km):
            return _snapshot(
                source_id="adsb-lol",
                label="adsb.lol",
                state=AircraftSnapshotState.LIVE,
            )

    class Secondary:
        provider_id = "airplanes-live"

        def fetch_snapshot(self, observer, radius_km):
            nonlocal secondary_calls
            secondary_calls += 1
            raise AssertionError("secondary must not be called when primary succeeds")

    monkeypatch.setattr(api_aircraft, "AdsbLolProvider", Primary)
    monkeypatch.setattr(api_aircraft, "AirplanesLiveProvider", Secondary)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=200&minimum_elevation_deg=-90"
    )
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()

    assert response.status_code == 200
    assert secondary_calls == 0
    assert response.json()["source"]["id"] == "adsb-lol"
    assert response.json()["source"]["provider_failover_used"] is False


def test_primary_unavailable_uses_secondary_snapshot(monkeypatch):
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()
    primary_calls = 0
    secondary_calls = 0

    class Primary:
        last_timings = {"provider_request_ms": 20.0, "provider_total_ms": 25.0}

        def fetch_snapshot(self, observer, radius_km):
            nonlocal primary_calls
            primary_calls += 1
            return _snapshot(
                source_id="adsb-lol",
                label="adsb.lol",
                state=AircraftSnapshotState.UNAVAILABLE,
            )

    class Secondary:
        provider_id = "airplanes-live"
        last_timings = {
            "provider_wait_ms": 5.0,
            "provider_throttle_ms": 7.0,
            "provider_request_ms": 30.0,
            "provider_total_ms": 45.0,
        }

        def fetch_snapshot(self, observer, radius_km):
            nonlocal secondary_calls
            secondary_calls += 1
            return _snapshot(
                source_id="airplanes-live",
                label="airplanes.live",
                state=AircraftSnapshotState.LIVE,
            )

    monkeypatch.setattr(api_aircraft, "AdsbLolProvider", Primary)
    monkeypatch.setattr(api_aircraft, "AirplanesLiveProvider", Secondary)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=400&minimum_elevation_deg=-90"
    )
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()

    assert response.status_code == 200
    assert primary_calls == 1
    assert secondary_calls == 1
    source = response.json()["source"]
    assert source["id"] == "airplanes-live"
    assert source["label"] == "airplanes.live"
    assert source["provider_failover_used"] is True
    timing = response.headers["Server-Timing"]
    assert "provider_request;dur=20.0" in timing
    assert "provider_failover_request;dur=30.0" in timing
    assert "provider_failover_total;dur=45.0" in timing


def test_both_providers_unavailable_returns_503(monkeypatch):
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()

    class Primary:
        last_timings = {"provider_request_ms": 20.0, "provider_total_ms": 25.0}

        def fetch_snapshot(self, observer, radius_km):
            return _snapshot(
                source_id="adsb-lol",
                label="adsb.lol",
                state=AircraftSnapshotState.UNAVAILABLE,
            )

    class Secondary:
        provider_id = "airplanes-live"
        last_timings = {"provider_request_ms": 30.0, "provider_total_ms": 35.0}

        def fetch_snapshot(self, observer, radius_km):
            return _snapshot(
                source_id="airplanes-live",
                label="airplanes.live",
                state=AircraftSnapshotState.UNAVAILABLE,
            )

    monkeypatch.setattr(api_aircraft, "AdsbLolProvider", Primary)
    monkeypatch.setattr(api_aircraft, "AirplanesLiveProvider", Secondary)

    response = TestClient(app).get(
        "/api/v1/aircraft?latitude=55.86&longitude=-4.25&radius_km=200"
    )
    api_aircraft._AIRCRAFT_SNAPSHOT_CACHE.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Aircraft data is temporarily unavailable"
    assert "provider_failover_request;dur=30.0" in response.headers["Server-Timing"]
