from datetime import datetime, timezone
from threading import Lock, Thread
import time

import httpx
import pytest

from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth.aircraft_adsb_lol import (
    AdsbLolProvider,
    FOOT_TO_M,
    KNOT_TO_MPS,
    _PROVIDER_REQUEST_CONCURRENCY,
    close_shared_adsb_http_client,
)


def test_adsb_lol_normalises_units_ages_and_identity_metadata():
    now = datetime.now(timezone.utc)
    payload = {
        "now": now.timestamp(),
        "ac": [
            {
                "hex": "40621d",
                "flight": "BAW123 ",
                "lat": 51.5,
                "lon": -0.1,
                "alt_baro": 10000,
                "alt_geom": 10100,
                "gs": 200,
                "track": 270,
                "baro_rate": 500,
                "squawk": "1234",
                "seen_pos": 2.0,
                "seen": 1.0,
                "r": "ZZ664",
                "t": "R135",
                "desc": "BOEING RC-135W RIVET JOINT",
                "ownOp": "ROYAL AIR FORCE",
                "dbFlags": 1,
            },
            {"hex": "bad", "lat": None, "lon": -0.2},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/point/51.500000/-0.100000/54"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(
        AircraftObserver(51.5, -0.1),
        100.0,
    )
    client.close()

    assert snapshot.state == AircraftSnapshotState.LIVE
    assert len(snapshot.observations) == 1
    aircraft = snapshot.observations[0]
    assert aircraft.callsign == "BAW123"
    assert aircraft.barometric_altitude_m == pytest.approx(10000 * FOOT_TO_M)
    assert aircraft.geometric_altitude_m == pytest.approx(10100 * FOOT_TO_M)
    assert aircraft.ground_speed_mps == pytest.approx(200 * KNOT_TO_MPS)
    assert aircraft.position_age_seconds(now) == pytest.approx(2.0, abs=0.1)
    assert aircraft.contact_age_seconds(now) == pytest.approx(1.0, abs=0.1)
    assert aircraft.registration == "ZZ664"
    assert aircraft.type_code == "R135"
    assert aircraft.type_description == "BOEING RC-135W RIVET JOINT"
    assert aircraft.operator == "ROYAL AIR FORCE"
    assert aircraft.military is True
    for stage in (
        "provider_client_ms",
        "provider_wait_ms",
        "provider_request_ms",
        "provider_decode_ms",
        "provider_close_ms",
        "provider_normalize_ms",
        "provider_total_ms",
    ):
        assert provider.last_timings[stage] >= 0.0
    assert provider.last_timings["provider_total_ms"] >= provider.last_timings[
        "provider_request_ms"
    ]


def test_default_providers_reuse_one_process_http_client(monkeypatch):
    from nightazimuth import aircraft_adsb_lol

    close_shared_adsb_http_client()
    created = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"now": datetime.now(timezone.utc).timestamp(), "ac": []}

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.is_closed = False
            self.urls = []
            created.append(self)

        def get(self, url):
            self.urls.append(url)
            return FakeResponse()

        def close(self):
            self.is_closed = True

    monkeypatch.setattr(aircraft_adsb_lol.httpx, "Client", FakeClient)
    try:
        first = AdsbLolProvider()
        second = AdsbLolProvider()
        first.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
        second.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)

        assert len(created) == 1
        assert len(created[0].urls) == 2
        assert created[0].is_closed is False
        assert first.last_timings["provider_client_ms"] >= 0.0
        assert second.last_timings["provider_client_ms"] >= 0.0
        assert first.last_timings["provider_wait_ms"] >= 0.0
        assert second.last_timings["provider_wait_ms"] >= 0.0
        assert first.last_timings["provider_close_ms"] >= 0.0
        assert second.last_timings["provider_close_ms"] >= 0.0
    finally:
        close_shared_adsb_http_client()

    assert created[0].is_closed is True


def test_adsb_provider_limits_simultaneous_outbound_requests():
    assert _PROVIDER_REQUEST_CONCURRENCY == 2
    active = 0
    maximum_active = 0
    state_lock = Lock()
    results = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"now": datetime.now(timezone.utc).timestamp(), "ac": []}

    class BlockingClient:
        def get(self, url):
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            try:
                time.sleep(0.05)
                return FakeResponse()
            finally:
                with state_lock:
                    active -= 1

    client = BlockingClient()

    def worker(index: int) -> None:
        provider = AdsbLolProvider(client=client)
        snapshot = provider.fetch_snapshot(
            AircraftObserver(51.0 + index * 0.01, -0.1),
            100.0,
        )
        results.append((snapshot, provider.last_timings))

    threads = [Thread(target=worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 4
    assert maximum_active == _PROVIDER_REQUEST_CONCURRENCY
    assert all(snapshot.state == AircraftSnapshotState.LIVE for snapshot, _ in results)
    assert sum(timings["provider_wait_ms"] > 10.0 for _, timings in results) >= 2


def test_adsb_lol_ground_contact_does_not_fabricate_barometric_altitude():
    now = datetime.now(timezone.utc)
    payload = {
        "now": now.timestamp(),
        "ac": [
            {
                "hex": "abcdef",
                "lat": 51.5,
                "lon": -0.1,
                "alt_baro": "ground",
                "seen": 0,
            }
        ],
    }

    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    snapshot = AdsbLolProvider(client=client).fetch_snapshot(
        AircraftObserver(51.5, -0.1),
        50.0,
    )
    client.close()

    aircraft = snapshot.observations[0]
    assert aircraft.on_ground is True
    assert aircraft.barometric_altitude_m is None


def test_adsb_lol_http_failure_returns_unavailable_snapshot():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, text="unavailable"))
    )
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(
        AircraftObserver(51.5, -0.1),
        50.0,
    )
    client.close()

    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert snapshot.observations == ()
    assert snapshot.error is not None
    assert provider.last_timings["provider_client_ms"] >= 0.0
    assert provider.last_timings["provider_wait_ms"] >= 0.0
    assert provider.last_timings["provider_request_ms"] >= 0.0
    assert provider.last_timings["provider_decode_ms"] == 0.0
    assert provider.last_timings["provider_close_ms"] >= 0.0
    assert provider.last_timings["provider_normalize_ms"] == 0.0
    assert provider.last_timings["provider_total_ms"] >= 0.0
