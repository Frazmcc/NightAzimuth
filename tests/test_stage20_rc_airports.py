from concurrent.futures import ThreadPoolExecutor
import threading
import time

import httpx

from nightazimuth.stage20_rc_airports import ResilientAirportLandmarkProvider, _Airport


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


def test_deploy_cache_avoids_runtime_airport_download(tmp_path) -> None:
    first_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, text=OURAIRPORTS_CSV)
        )
    )
    build_provider = ResilientAirportLandmarkProvider(
        client=first_client,
        cache_directory=tmp_path,
    )
    assert build_provider.preload() == 2
    first_client.close()

    cache_path = tmp_path / "airports" / "ourairports.csv"
    assert cache_path.exists()

    def no_network(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("runtime should load the deploy-cached airport catalogue")

    runtime_client = httpx.Client(transport=httpx.MockTransport(no_network))
    runtime_provider = ResilientAirportLandmarkProvider(
        client=runtime_client,
        cache_directory=tmp_path,
    )
    airports = runtime_provider.nearby(0.0, 0.0, max_distance_km=100.0, limit=10)
    runtime_client.close()

    assert [item.iata for item in airports] == ["BBB", "AAA"]


def test_concurrent_cold_load_fetches_global_catalogue_once(monkeypatch) -> None:
    provider = ResilientAirportLandmarkProvider()
    records = (
        _Airport(
            iata="AAA",
            icao="AAAA",
            name="Alpha",
            latitude_deg=0.0,
            longitude_deg=0.0,
            airport_type="large_airport",
            scheduled_service=True,
        ),
    )
    calls = 0
    guard = threading.Lock()

    def fetch_once():
        nonlocal calls
        with guard:
            calls += 1
        time.sleep(0.05)
        return records

    monkeypatch.setattr(provider, "_fetch_ourairports", fetch_once)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: provider._load_records(), range(2)))

    assert results == [records, records]
    assert calls == 1
