from datetime import datetime, timezone

import httpx
import pytest

from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState, AircraftSourceKind
from nightazimuth.aircraft_adsb_lol import FOOT_TO_M, KNOT_TO_MPS
from nightazimuth.aircraft_readsb import ReadsbProvider


def test_readsb_provider_uses_configured_endpoint_and_normalises_records():
    now = datetime.now(timezone.utc)
    payload = {
        "now": now.timestamp(),
        "aircraft": [
            {
                "hex": "4ca123",
                "flight": "RCH123 ",
                "lat": 55.85,
                "lon": -4.25,
                "alt_baro": 12000,
                "alt_geom": 12100,
                "gs": 230,
                "track": 90,
                "geom_rate": -300,
                "seen_pos": 1.5,
                "seen": 0.5,
                "r": "62-3565",
                "t": "K35R",
                "desc": "BOEING KC-135R STRATOTANKER",
                "ownOp": "UNITED STATES AIR FORCE",
                "dbFlags": 1,
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://receiver.local/data/aircraft.json"
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ReadsbProvider("http://receiver.local/data/aircraft.json", client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(55.86, -4.25), 100.0)
    client.close()

    assert snapshot.state == AircraftSnapshotState.LIVE
    assert snapshot.coverage_description == "local receiver coverage"
    assert len(snapshot.observations) == 1
    aircraft = snapshot.observations[0]
    assert aircraft.source_kind == AircraftSourceKind.LOCAL
    assert aircraft.callsign == "RCH123"
    assert aircraft.barometric_altitude_m == pytest.approx(12000 * FOOT_TO_M)
    assert aircraft.ground_speed_mps == pytest.approx(230 * KNOT_TO_MPS)
    assert aircraft.registration == "62-3565"
    assert aircraft.type_code == "K35R"
    assert aircraft.type_description == "BOEING KC-135R STRATOTANKER"
    assert aircraft.operator == "UNITED STATES AIR FORCE"
    assert aircraft.military is True


def test_readsb_provider_rejects_non_http_endpoint():
    with pytest.raises(ValueError):
        ReadsbProvider("receiver.local/data/aircraft.json")


def test_readsb_failure_is_non_fatal_unavailable_snapshot():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="error"))
    )
    provider = ReadsbProvider("http://receiver.local/data/aircraft.json", client=client)
    snapshot = provider.fetch_snapshot(AircraftObserver(55.86, -4.25), 100.0)
    client.close()

    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert snapshot.error is not None
    assert snapshot.observations == ()
