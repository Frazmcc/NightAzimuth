from datetime import datetime, timezone

import httpx

from nightazimuth import aircraft_adsb_lol
from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth.aircraft_adsb_lol import AirplanesLiveProvider


def test_adsb_fi_failover_uses_documented_point_endpoint_and_preserves_source(monkeypatch):
    payload = {
        "now": datetime.now(timezone.utc).timestamp(),
        "aircraft": [
            {
                "hex": "abc123",
                "flight": "TEST1",
                "lat": 51.5,
                "lon": -0.1,
                "alt_baro": 10000,
                "seen": 0,
                "seen_pos": 0,
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "opendata.adsb.fi"
        assert request.url.path == "/api/v3/lat/51.500000/lon/-0.100000/dist/54"
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_MIN_START_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(aircraft_adsb_lol, "_PROVIDER_NEXT_REQUEST_AT", 0.0)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AirplanesLiveProvider(client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)
    client.close()

    assert snapshot.state == AircraftSnapshotState.LIVE
    assert snapshot.source_id == "adsb-fi"
    assert "adsb.fi" in snapshot.source_label
    assert "https://adsb.fi/" in snapshot.source_label
    assert len(snapshot.observations) == 1
    assert snapshot.observations[0].source_id == "adsb-fi"
    assert snapshot.observations[0].source_label == snapshot.source_label
    assert provider.last_timings["provider_retry_count"] == 0.0
