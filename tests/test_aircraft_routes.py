import httpx

from nightazimuth.aircraft_routes import AdsbLolRouteProvider


PAYLOAD = {
    "callsign": "BAW123",
    "number": "123",
    "airline_code": "BAW",
    "airport_codes": "EGLL-KJFK",
    "_airport_codes_iata": "LHR-JFK",
    "_airports": [
        {
            "name": "London Heathrow Airport",
            "icao": "EGLL",
            "iata": "LHR",
            "location": "London",
            "countryiso2": "GB",
            "lat": 51.4706,
            "lon": -0.4619,
            "alt_feet": 83.0,
        },
        {
            "name": "John F Kennedy International Airport",
            "icao": "KJFK",
            "iata": "JFK",
            "location": "New York",
            "countryiso2": "US",
            "lat": 40.6398,
            "lon": -73.7789,
            "alt_feet": 13.0,
        },
    ],
}


def test_route_provider_returns_departure_and_arrival_airport_details():
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=PAYLOAD)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolRouteProvider(client=client)
    route = provider.lookup(" baw123 ")
    client.close()

    assert route is not None
    assert route.callsign == "BAW123"
    assert route.airline_code == "BAW"
    assert route.departure is not None
    assert route.departure.name == "London Heathrow Airport"
    assert route.departure.display_code == "LHR / EGLL"
    assert route.departure.display_country == "GB"
    assert route.arrival is not None
    assert route.arrival.name == "John F Kennedy International Airport"
    assert route.arrival.display_code == "JFK / KJFK"
    assert route.arrival.display_country == "US"
    assert seen_urls == [
        "https://vrs-standing-data.adsb.lol/routes/BA/BAW123.json"
    ]


def test_route_provider_caches_successful_lookup():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=PAYLOAD)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolRouteProvider(client=client)
    first = provider.lookup("BAW123")
    second = provider.lookup("BAW123")
    client.close()

    assert first == second
    assert calls == 1


def test_route_provider_negative_caches_missing_route():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolRouteProvider(client=client)
    assert provider.lookup("ZZZ999") is None
    assert provider.lookup("ZZZ999") is None
    client.close()

    assert calls == 1


def test_route_provider_rejects_invalid_callsign_without_network_request():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AdsbLolRouteProvider(client=client)
    assert provider.lookup(None) is None
    assert provider.lookup("?") is None
    assert provider.lookup("BAW/123") is None
    client.close()

    assert calls == 0


def test_incomplete_route_is_not_presented_as_known():
    payload = dict(PAYLOAD)
    payload["_airports"] = PAYLOAD["_airports"][:1]
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    provider = AdsbLolRouteProvider(client=client)
    assert provider.lookup("BAW123") is None
    client.close()
