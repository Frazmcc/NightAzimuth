import httpx

from nightazimuth.stage20_rc_airports import ResilientAirportLandmarkProvider


OURAIRPORTS_CSV = (
    "ident,type,name,latitude_deg,longitude_deg,scheduled_service,iata_code\n"
    "AAAA,medium_airport,Alpha Regional,0.20,0.10,yes,AAA\n"
    "BBBB,large_airport,Bravo International,0.55,0.00,yes,BBB\n"
    "CCCC,small_airport,Charlie Strip,0.05,0.00,no,CCC\n"
)

ADSB_CSV = (
    "Code,Name,ICAO,IATA,Location,CountryISO2,Latitude,Longitude,AltitudeFeet\n"
    "AAAA,Alpha Airport,AAAA,AAA,Alpha,ZZ,0.20,0.10,100\n"
    "BBBB,Bravo Airport,BBBB,BBB,Bravo,ZZ,0.55,0.00,100\n"
)


def test_primary_provider_prefers_significant_airports() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "ourairports" in str(request.url)
        return httpx.Response(200, text=OURAIRPORTS_CSV)

    provider = ResilientAirportLandmarkProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    airports = provider.nearby(0.0, 0.0, max_distance_km=100.0, limit=10)

    assert [item.iata for item in airports] == ["BBB", "AAA"]


def test_adsb_lol_fallback_is_used_when_primary_fails() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if "ourairports" in str(request.url):
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, text=ADSB_CSV)

    provider = ResilientAirportLandmarkProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    airports = provider.nearby(0.0, 0.0, max_distance_km=100.0, limit=10)

    assert [item.iata for item in airports] == ["AAA", "BBB"]
    assert any("airports.csv" in url and "adsb.lol" in url for url in requested)


def test_airport_selection_uses_runtime_observer_location() -> None:
    csv_text = (
        "ident,type,name,latitude_deg,longitude_deg,scheduled_service,iata_code\n"
        "AAAA,large_airport,West Airport,0.0,-0.20,yes,AAA\n"
        "BBBB,large_airport,East Airport,0.0,2.00,yes,BBB\n"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=csv_text)

    provider = ResilientAirportLandmarkProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    near_west = provider.nearby(0.0, 0.0, max_distance_km=100.0, limit=10)
    near_east = provider.nearby(0.0, 1.8, max_distance_km=100.0, limit=10)

    assert [item.iata for item in near_west] == ["AAA"]
    assert [item.iata for item in near_east] == ["BBB"]
