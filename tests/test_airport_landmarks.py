import gzip

import httpx

from nightazimuth.airport_landmarks import AirportLandmarkProvider, airport_in_view


def _provider() -> AirportLandmarkProvider:
    csv_text = (
        "Code,Name,ICAO,IATA,Location,CountryISO2,Latitude,Longitude,AltitudeFeet\n"
        "A,Alpha International,AAAA,AAA,Alpha,ZZ,0.20,0.10,100\n"
        "B,Bravo International,BBBB,BBB,Bravo,ZZ,0.55,0.00,100\n"
        "C,Charlie International,CCCC,CCC,Charlie,ZZ,1.10,0.00,100\n"
        "D,Delta International,DDDD,DDD,Delta,ZZ,2.80,0.00,100\n"
        "E,Local Strip,EEEE,,Echo,ZZ,0.05,0.00,100\n"
    )
    payload = gzip.compress(csv_text.encode("utf-8"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AirportLandmarkProvider(client=client)


def test_airports_are_derived_from_runtime_dataset_and_observer_location() -> None:
    airports = _provider().nearby(0.0, 0.0, max_distance_km=140.0, limit=4)
    assert [airport.iata for airport in airports] == ["AAA", "BBB", "CCC"]


def test_airport_visibility_respects_current_view_sector() -> None:
    airport = _provider().nearby(0.0, 0.0, max_distance_km=100.0, limit=1)[0]
    assert airport_in_view(airport, airport.bearing_deg, 60.0)
    assert not airport_in_view(airport, (airport.bearing_deg + 180.0) % 360.0, 60.0)


def test_airport_selection_is_distance_limited_sparse_and_ignores_non_iata_rows() -> None:
    airports = _provider().nearby(0.0, 0.0, max_distance_km=80.0, limit=2)
    assert [airport.iata for airport in airports] == ["AAA", "BBB"]
