from datetime import datetime, timezone
from threading import Event, Lock, Thread

import httpx

from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth import aircraft_adsb_lol
from nightazimuth.aircraft_adsb_lol import AdsbLolProvider


def _live_payload():
    return {"now": datetime.now(timezone.utc).timestamp(), "ac": []}


def test_transient_provider_failure_is_retried_once(monkeypatch):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporary")
        return httpx.Response(200, json=_live_payload())

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
    client.close()

    assert calls == 2
    assert snapshot.state == AircraftSnapshotState.LIVE
    assert provider.last_timings["provider_retry_count"] == 1.0
    assert provider.last_timings["provider_retry_wait_ms"] >= 0.0


def test_persistent_transient_failure_stops_after_one_retry(monkeypatch):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="temporary")

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
    client.close()

    assert calls == 2
    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert provider.last_timings["provider_retry_count"] == 1.0


def test_non_retryable_provider_failure_is_not_retried(monkeypatch):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, text="not found")

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
    client.close()

    assert calls == 1
    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert provider.last_timings["provider_retry_count"] == 0.0


def test_provider_start_spacing_is_observable(monkeypatch):
    clock = [100.0]

    def fake_monotonic() -> float:
        return clock[0]

    def fake_sleep(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.02)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "monotonic", fake_monotonic)
    monkeypatch.setattr(aircraft_adsb_lol, "sleep", fake_sleep)

    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=_live_payload()))
    )
    first = AdsbLolProvider(client=client)
    second = AdsbLolProvider(client=client)

    first.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
    second.fetch_snapshot(AircraftObserver(52.0, -0.2), 100.0)
    client.close()

    assert first.last_timings["provider_throttle_ms"] == 0.0
    assert 19.9 <= second.last_timings["provider_throttle_ms"] <= 20.1


def test_retry_backoff_releases_gate_for_other_region(monkeypatch):
    first_failure_seen = Event()
    sequence: list[str] = []
    sequence_lock = Lock()
    first_region_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal first_region_calls
        path = request.url.path
        with sequence_lock:
            sequence.append(path)
        if "/51.500000/" in path:
            first_region_calls += 1
            if first_region_calls == 1:
                first_failure_seen.set()
                return httpx.Response(503, text="temporary")
        return httpx.Response(200, json=_live_payload())

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.05)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = AdsbLolProvider(client=client)
    second = AdsbLolProvider(client=client)
    snapshots: dict[str, object] = {}

    first_thread = Thread(
        target=lambda: snapshots.setdefault(
            "first", first.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
        )
    )
    second_thread = Thread(
        target=lambda: snapshots.setdefault(
            "second", second.fetch_snapshot(AircraftObserver(52.0, -0.2), 100.0)
        )
    )

    first_thread.start()
    assert first_failure_seen.wait(timeout=1.0)
    second_thread.start()
    first_thread.join(timeout=2.0)
    second_thread.join(timeout=2.0)
    client.close()

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert ["/51.500000/" in path for path in sequence] == [True, False, True]
    assert snapshots["first"].state == AircraftSnapshotState.LIVE
    assert snapshots["second"].state == AircraftSnapshotState.LIVE
