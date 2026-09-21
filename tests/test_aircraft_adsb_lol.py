from datetime import datetime, timezone

import httpx
import pytest

from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth.aircraft_adsb_lol import AdsbLolProvider, FOOT_TO_M, KNOT_TO_MPS


def test_adsb_lol_normalises_units_and_ages():
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
            },
            {"hex": "bad", "lat": None, "lon": -0.2},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/dist/54" in str(request.url)
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    snapshot = AdsbLolProvider(client=client).fetch_snapshot(
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
    snapshot = AdsbLolProvider(client=client).fetch_snapshot(
        AircraftObserver(51.5, -0.1),
        50.0,
    )
    client.close()

    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert snapshot.observations == ()
    assert snapshot.error is not None
