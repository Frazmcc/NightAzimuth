from __future__ import annotations

import httpx

from nightazimuth import aircraft_adsb_lol
from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth.aircraft_adsb_lol import AdsbLolProvider
from nightazimuth.api_aircraft import _server_timing


def test_adsb_provider_records_final_http_status(monkeypatch) -> None:
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_RETRY_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)

    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="limited"))
    )
    provider = AdsbLolProvider(client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 50.0)
    client.close()

    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert provider.last_timings["provider_status_code"] == 429.0


def test_server_timing_exposes_provider_status() -> None:
    timing = _server_timing({"provider_status_code": 503.0}, 12.5)

    assert 'provider_status;desc="503"' in timing
    assert "total;dur=12.5" in timing
