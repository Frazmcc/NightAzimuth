from __future__ import annotations

from datetime import UTC, datetime

import httpx

from nightazimuth.config import ObserverConfig
from nightazimuth.roadster_ephemeris import (
    RoadsterEphemerisProvider,
    parse_horizons_observer_result,
    roadster_from_horizons_fields,
)


HORIZONS_RESULT = """
*******************************************************************************
 Date__(UT)__HR:MN:SS, , , R.A._(a-appar), DEC., Azimuth_(a-app), Elevation_(a-app), APmag, S-brt, hEcl-Lon, hEcl-Lat, r, rdot, delta, deldot, 1-way_down_LT, VmagSn, VmagOb, S-O-T, /r, S-T-O, Cnst
*******************************************************************************
$$SOE
 2026-Oct-02 00:00:00,*,m,190.123456,-5.500000,210.125000,20.250000,n.a.,n.a.,15.25,-1.75,1.421,4.2,2.345,-7.8,19.50,32.1,21.4,92.5,/T,35.2,Vir
$$EOE
*******************************************************************************
"""


def test_horizons_csv_parser_preserves_named_quantities() -> None:
    fields = parse_horizons_observer_result(HORIZONS_RESULT)

    assert fields["raaappar"] == "190.123456"
    assert fields["dec"] == "-5.500000"
    assert fields["azimuthaapp"] == "210.125000"
    assert fields["elevationaapp"] == "20.250000"
    assert fields["delta"] == "2.345"
    assert fields["r"] == "1.421"
    assert fields["r_2"] == "/T"


def test_roadster_payload_contains_observer_and_deep_space_context() -> None:
    fields = parse_horizons_observer_result(HORIZONS_RESULT)
    result = roadster_from_horizons_fields(
        fields,
        when=datetime(2026, 10, 2, 0, 0, tzinfo=UTC),
    )

    assert result.id == "tesla-roadster-starman"
    assert result.jpl_target_id == "-143205"
    assert result.international_designator == "2018-017A"
    assert result.azimuth_deg == 210.125
    assert result.elevation_deg == 20.25
    assert result.distance_earth_au == 2.345
    assert result.distance_earth_km is not None
    assert result.distance_earth_km > 300_000_000
    assert result.distance_sun_au == 1.421
    assert result.earth_range_rate_km_s == -7.8
    assert result.light_time_minutes == 19.5
    assert result.heliocentric_speed_km_s == 32.1
    assert result.solar_elongation_deg == 92.5
    assert result.phase_angle_deg == 35.2
    assert result.apparent_magnitude is None
    assert result.constellation == "Vir"
    assert "not live telemetry" in result.tracking_mode


def test_provider_caches_observer_ephemeris_without_repeated_jpl_requests() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"result": HORIZONS_RESULT})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = RoadsterEphemerisProvider(client=client, cache_minutes=10)
        observer = ObserverConfig(latitude=55.86, longitude=-4.25, altitude_m=45.0)
        when = datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
        first = provider.lookup(observer, when=when)
        second = provider.lookup(observer, when=when)

    assert first is not None
    assert second == first
    assert len(calls) == 1
    query = calls[0].url.params
    assert query["COMMAND"] == "'-143205'"
    assert query["EPHEM_TYPE"] == "'OBSERVER'"
    assert query["CENTER"] == "'coord@399'"
    assert query["SITE_COORD"].startswith("'-4.250000,55.860000,")
    assert query["QUANTITIES"] == "'2,4,9,18,19,20,21,22,23,24,29'"


def test_provider_fails_soft_when_horizons_is_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = RoadsterEphemerisProvider(client=client)
        observer = ObserverConfig(latitude=55.86, longitude=-4.25)
        result = provider.lookup(observer, when=datetime(2026, 10, 2, tzinfo=UTC))

    assert result is None
