import gzip

import httpx

from nightazimuth.airport_landmarks import AirportLandmarkProvider, airport_in_view


def _provider(*, compressed: bool = False) -> AirportLandmarkProvider:
    csv_text = (
        "ident,type,name,latitude_deg,longitude_deg,scheduled_service,iata_code\n"
        "AAAA,medium_airport,Alpha Regional,0.20,0.10,yes,AAA\n"
        "BBBB,large_airport,Bravo International,0.55,0.00,yes,BBB\n"
        "CCCC,large_airport,Charlie International,1.10,0.00,yes,CCC\n"
        "DDDD,large_airport,Delta International,2.80,0.00,yes,DDD\n"
        "EEEE,small_airport,Local Strip,0.05,0.00,no,EEE\n"
        "FFFF,heliport,City Heliport,0.08,0.00,no,FFF\n"
    )
    payload = csv_text.encode("utf-8")
    if compressed:
        payload = gzip.compress(payload)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AirportLandmarkProvider(client=client)


def test_airports_are_derived_from_runtime_dataset_and_observer_location() -> None:
    airports = _provider().nearby(0.0, 0.0, max_distance_km=140.0, limit=4)
    assert [airport.iata for airport in airports] == ["BBB", "CCC", "AAA", "EEE"]


def test_airport_visibility_respects_current_view_sector() -> None:
    airport = _provider().nearby(0.0, 0.0, max_distance_km=100.0, limit=1)[0]
    assert airport_in_view(airport, airport.bearing_deg, 60.0)
    assert not airport_in_view(airport, (airport.bearing_deg + 180.0) % 360.0, 60.0)


def test_large_airports_are_preferred_over_closer_small_airports() -> None:
    airports = _provider().nearby(0.0, 0.0, max_distance_km=80.0, limit=2)
    assert [airport.iata for airport in airports] == ["BBB", "AAA"]


def test_provider_accepts_gzip_payload_without_assuming_the_endpoint_is_gzipped() -> None:
    airports = _provider(compressed=True).nearby(0.0, 0.0, max_distance_km=80.0, limit=1)
    assert airports[0].iata == "BBB"


def test_non_airport_types_are_excluded() -> None:
    airports = _provider().nearby(0.0, 0.0, max_distance_km=20.0, limit=10)
    assert "FFF" not in {airport.iata for airport in airports}
