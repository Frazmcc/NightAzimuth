from datetime import datetime

import pytest

from nightazimuth.aircraft import (
    FEET_TO_METRES,
    AircraftPosition,
    aircraft_sightline,
    parse_readsb_aircraft,
    project_aircraft_position,
)


def test_parser_prefers_geometric_altitude_and_keeps_track_heading_distinct() -> None:
    rows = parse_readsb_aircraft(
        {
            "ac": [
                {
                    "hex": "abc123",
                    "flight": " TEST1 ",
                    "lat": 0.01,
                    "lon": 0.02,
                    "alt_geom": 12_000,
                    "alt_baro": 11_700,
                    "gs": 240,
                    "track": 91,
                    "true_heading": 84,
                    "geom_rate": 500,
                    "seen_pos": 1.5,
                }
            ]
        }
    )

    assert len(rows) == 1
    aircraft = rows[0]
    assert aircraft.callsign == "TEST1"
    assert aircraft.altitude_m == pytest.approx(12_000 * FEET_TO_METRES)
    assert aircraft.altitude_source == "geometric"
    assert aircraft.ground_track_deg == 91
    assert aircraft.true_heading_deg == 84


def test_parser_uses_labelled_baro_fallback_and_rejects_old_or_ground_positions() -> None:
    rows = parse_readsb_aircraft(
        {
            "aircraft": [
                {"hex": "fresh", "lat": 1, "lon": 2, "alt_baro": 8_000, "seen": 2},
                {"hex": "old", "lat": 1, "lon": 2, "alt_baro": 8_000, "seen_pos": 31},
                {"hex": "ground", "lat": 1, "lon": 2, "alt_baro": "ground", "seen_pos": 0},
                {"hex": "missing", "alt_baro": 8_000, "seen_pos": 0},
            ]
        }
    )

    assert [row.hex_id for row in rows] == ["fresh"]
    assert rows[0].altitude_source == "barometric"


def test_same_latitude_longitude_above_observer_is_overhead() -> None:
    aircraft = _aircraft(latitude=0, longitude=0, altitude_m=10_000)
    line = aircraft_sightline(
        aircraft,
        observer_latitude=0,
        observer_longitude=0,
        observer_altitude_m=0,
    )
    assert line.elevation_deg == pytest.approx(90)
    assert line.slant_range_km == pytest.approx(10)


def test_east_and_north_positions_have_correct_true_azimuths() -> None:
    east = aircraft_sightline(
        _aircraft(latitude=0, longitude=0.1, altitude_m=10_000),
        observer_latitude=0,
        observer_longitude=0,
        observer_altitude_m=0,
    )
    north = aircraft_sightline(
        _aircraft(latitude=0.1, longitude=0, altitude_m=10_000),
        observer_latitude=0,
        observer_longitude=0,
        observer_altitude_m=0,
    )
    assert east.azimuth_deg == pytest.approx(90, abs=0.1)
    assert north.azimuth_deg == pytest.approx(0, abs=0.1)
    assert east.elevation_deg > 0
    assert north.elevation_deg > 0


def test_observer_altitude_is_used() -> None:
    line = aircraft_sightline(
        _aircraft(latitude=0, longitude=0, altitude_m=1_000),
        observer_latitude=0,
        observer_longitude=0,
        observer_altitude_m=2_000,
    )
    assert line.elevation_deg == pytest.approx(-90)


def test_short_projection_uses_ground_track_speed_and_vertical_rate() -> None:
    aircraft = _aircraft(
        latitude=0,
        longitude=0,
        altitude_m=1_000,
        ground_speed_knots=360,
        ground_track_deg=90,
        true_heading_deg=75,
        vertical_rate_fpm=600,
    )
    future = project_aircraft_position(aircraft, 60)
    assert future.longitude > aircraft.longitude
    assert future.latitude == pytest.approx(aircraft.latitude, abs=0.001)
    assert future.altitude_m == pytest.approx(aircraft.altitude_m + 600 * FEET_TO_METRES)
    assert future.true_heading_deg == 75


def _aircraft(**changes: object) -> AircraftPosition:
    values = {
        "hex_id": "abc123",
        "callsign": "TEST1",
        "registration": None,
        "aircraft_type": None,
        "latitude": 0.0,
        "longitude": 0.0,
        "altitude_m": 3_000.0,
        "altitude_source": "geometric",
        "ground_speed_knots": None,
        "ground_track_deg": None,
        "true_heading_deg": None,
        "vertical_rate_fpm": None,
        "position_age_seconds": 1.0,
    }
    values.update(changes)
    return AircraftPosition(**values)
