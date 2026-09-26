from datetime import datetime, timezone

import httpx
import pytest

from nightazimuth.aircraft import AircraftObserver
from nightazimuth.aircraft_adsb_lol import AdsbLolProvider


def test_provider_uses_documented_point_endpoint_and_last_position_fallback() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "now": now.timestamp(),
        "ac": [
            {
                "hex": "40621d",
                "flight": "TEST123",
                "lat": None,
                "lon": None,
                "lastPosition": {
                    "lat": 55.90,
                    "lon": -4.20,
                    "seen_pos": 12.0,
                },
                "alt_baro": 12000,
                "seen": 1.0,
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/point/55.860000/-4.250000/54"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    snapshot = AdsbLolProvider(client=client).fetch_snapshot(
        AircraftObserver(55.86, -4.25),
        100.0,
    )
    client.close()

    assert len(snapshot.observations) == 1
    aircraft = snapshot.observations[0]
    assert aircraft.latitude_deg == pytest.approx(55.90)
    assert aircraft.longitude_deg == pytest.approx(-4.20)
    assert aircraft.position_age_seconds(now) == pytest.approx(12.0, abs=0.2)
