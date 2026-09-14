import json

import httpx
import pytest

from nightazimuth.aircraft_preferences import (
    AIRCRAFT_SOURCES,
    AircraftPreferences,
    AircraftPreferenceStore,
)
from nightazimuth.aircraft_providers import (
    ADSB_LOL_ATTRIBUTION,
    AdsbLolAircraftProvider,
    LocalReadsbAircraftProvider,
    USER_AGENT,
    validate_local_receiver_url,
)


def _response(request: httpx.Request) -> httpx.Response:
    payload = {
        "ac": [
            {
                "hex": "abc123",
                "flight": "TEST1",
                "lat": 0.1,
                "lon": 0.2,
                "alt_geom": 10_000,
                "seen_pos": 1,
            }
        ]
    }
    return httpx.Response(200, request=request, content=json.dumps(payload).encode())


def test_adsb_lol_provider_uses_keyless_point_endpoint_and_attribution() -> None:
    with httpx.Client(transport=httpx.MockTransport(_response)) as client:
        snapshot = AdsbLolAircraftProvider(client=client).load(1.0, 2.0, 40.0)

    assert len(snapshot.aircraft) == 1
    assert snapshot.source_name == "ADSB.lol"
    assert snapshot.attribution == ADSB_LOL_ATTRIBUTION


def test_adsb_lol_request_contains_no_api_key() -> None:
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request)

    with httpx.Client(transport=httpx.MockTransport(capture)) as client:
        AdsbLolAircraftProvider(client=client).load(1.0, 2.0, 40.0)

    request = requests[0]
    assert request.url.path == "/v2/point/1.000000/2.000000/40.0"
    assert request.url.query == b""
    assert request.headers["User-Agent"] == USER_AGENT
    assert "key" not in request.headers


def test_local_provider_reads_exact_configured_aircraft_json_url() -> None:
    requests: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(request)

    url = "http://127.0.0.1:8080/data/aircraft.json"
    with httpx.Client(transport=httpx.MockTransport(capture)) as client:
        snapshot = LocalReadsbAircraftProvider(url, client=client).load(1, 2, 40)

    assert str(requests[0].url) == url
    assert snapshot.source_name == "Local readsb/dump1090"


def test_local_provider_enforces_configured_radius() -> None:
    def response(request: httpx.Request) -> httpx.Response:
        payload = {
            "aircraft": [
                {
                    "hex": "near01",
                    "lat": 0.1,
                    "lon": 0.0,
                    "alt_geom": 10_000,
                    "seen_pos": 1,
                },
                {
                    "hex": "far001",
                    "lat": 2.0,
                    "lon": 0.0,
                    "alt_geom": 10_000,
                    "seen_pos": 1,
                },
            ]
        }
        return httpx.Response(200, request=request, content=json.dumps(payload).encode())

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        snapshot = LocalReadsbAircraftProvider(client=client).load(0, 0, 40)

    assert [aircraft.hex_id for aircraft in snapshot.aircraft] == ["near01"]


@pytest.mark.parametrize(
    "url",
    ["", "ftp://receiver/aircraft.json", "receiver/aircraft.json", "http://user:secret@receiver/data"],
)
def test_local_receiver_url_rejects_invalid_or_credentialed_values(url: str) -> None:
    with pytest.raises(ValueError):
        validate_local_receiver_url(url)


def test_aircraft_preferences_round_trip_without_positions(tmp_path) -> None:
    path = tmp_path / "aircraft-preferences.json"
    store = AircraftPreferenceStore(path)
    expected = AircraftPreferences(
        source=AIRCRAFT_SOURCES[1],
        local_receiver_url="http://192.0.2.10/data/aircraft.json",
        radius_nm=25,
    )
    store.save(expected)

    assert store.load() == expected
    text = path.read_text(encoding="utf-8")
    assert "latitude" not in text
    assert "longitude" not in text
    assert "aircraft" not in text.casefold().replace("aircraft-preferences", "")
