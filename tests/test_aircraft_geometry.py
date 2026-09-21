from datetime import datetime, timezone

import pytest

from nightazimuth.aircraft import AircraftObservation, AircraftObserver, AircraftSourceKind
from nightazimuth.aircraft_geometry import aircraft_sky_position


def _aircraft(*, lat: float, lon: float, baro: float | None, geom: float | None):
    return AircraftObservation(
        icao24="40621d",
        callsign="TEST1",
        latitude_deg=lat,
        longitude_deg=lon,
        barometric_altitude_m=baro,
        geometric_altitude_m=geom,
        ground_speed_mps=100.0,
        track_deg=90.0,
        vertical_rate_mps=0.0,
        squawk=None,
        on_ground=False,
        position_observed_at=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
        contact_observed_at=None,
        source_id="test",
        source_label="Test",
        source_kind=AircraftSourceKind.INTERNET,
    )


def test_aircraft_directly_above_observer_is_near_zenith():
    observer = AircraftObserver(55.0, -4.0, altitude_m=100.0)
    aircraft = _aircraft(lat=55.0, lon=-4.0, baro=None, geom=1100.0)

    sky = aircraft_sky_position(observer, aircraft)

    assert sky is not None
    assert sky.elevation_deg == pytest.approx(90.0, abs=1e-6)
    assert sky.slant_range_m == pytest.approx(1000.0, abs=0.05)
    assert sky.altitude_source == "geometric"


def test_aircraft_due_east_has_eastward_azimuth():
    observer = AircraftObserver(0.0, 0.0, altitude_m=0.0)
    aircraft = _aircraft(lat=0.0, lon=0.01, baro=1000.0, geom=None)

    sky = aircraft_sky_position(observer, aircraft)

    assert sky is not None
    assert sky.azimuth_deg == pytest.approx(90.0, abs=0.05)
    assert sky.elevation_deg > 0.0
    assert sky.altitude_source == "barometric"


def test_geometry_returns_none_when_aircraft_has_no_altitude():
    observer = AircraftObserver(55.0, -4.0, altitude_m=100.0)
    aircraft = _aircraft(lat=55.1, lon=-4.0, baro=None, geom=None)

    assert aircraft_sky_position(observer, aircraft) is None
