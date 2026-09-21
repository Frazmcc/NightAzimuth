import math

import pytest

from nightazimuth.aircraft_hud_finder_view import (
    _aircraft_colour,
    _aircraft_display_colour,
    _triangle_points,
    centred_elevation_window,
    interpolated_aircraft_sky_position,
)
from nightazimuth.aircraft_live import AircraftSkyTrackPoint, SkyAircraft
from nightazimuth.aircraft_motion import AircraftPositionState
from nightazimuth.aircraft_squawk import classify_squawk


def _aircraft_with_track(*, squawk: str | None = None) -> SkyAircraft:
    return SkyAircraft(
        icao24="40621d",
        callsign="TEST1",
        azimuth_deg=350.0,
        elevation_deg=20.0,
        range_km=10.0,
        altitude_m=1000.0,
        track_deg=90.0,
        ground_speed_mps=100.0,
        vertical_rate_mps=0.0,
        squawk=squawk,
        squawk_alert=classify_squawk(squawk),
        position_state=AircraftPositionState.MEASURED,
        position_age_seconds=0.0,
        source_id="test",
        source_label="Test",
        future_track=(
            AircraftSkyTrackPoint(0.0, 350.0, 20.0),
            AircraftSkyTrackPoint(10.0, 10.0, 30.0),
        ),
    )


def test_triangle_tip_follows_requested_direction():
    points = _triangle_points(100.0, 50.0, 10.0, (1.0, 0.0))
    assert points[0] == 110.0
    assert points[1] == 50.0


def test_triangle_geometry_is_finite():
    points = _triangle_points(0.0, 0.0, 5.0, (0.0, -1.0))
    assert len(points) == 6
    assert all(math.isfinite(value) for value in points)


def test_aircraft_colour_distinguishes_estimated_and_stale_positions():
    measured = _aircraft_colour(AircraftPositionState.MEASURED)
    interpolated = _aircraft_colour(AircraftPositionState.INTERPOLATED)
    estimated = _aircraft_colour(AircraftPositionState.EXTRAPOLATED)
    stale = _aircraft_colour(AircraftPositionState.STALE)
    assert measured == interpolated
    assert estimated != measured
    assert stale != measured
    assert stale != estimated


def test_critical_squawk_overrides_normal_position_colour():
    normal = _aircraft_display_colour(_aircraft_with_track())
    emergency = _aircraft_display_colour(_aircraft_with_track(squawk="7700"))
    assert emergency != normal
    assert emergency == "#ef4444"


def test_aircraft_sky_animation_wraps_cleanly_across_north():
    azimuth, elevation = interpolated_aircraft_sky_position(_aircraft_with_track(), 5.0)
    assert azimuth == pytest.approx(0.0)
    assert elevation == pytest.approx(25.0)


def test_centred_elevation_window_preserves_span_and_clamps_horizon():
    minimum, maximum = centred_elevation_window(5.0, 20.0, 70.0)
    assert minimum == 0.0
    assert maximum == 50.0


def test_centred_elevation_window_clamps_at_zenith():
    minimum, maximum = centred_elevation_window(88.0, 20.0, 70.0)
    assert minimum == 40.0
    assert maximum == 90.0
