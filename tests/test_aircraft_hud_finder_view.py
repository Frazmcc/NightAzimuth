import math

from nightazimuth.aircraft_hud_finder_view import _aircraft_colour, _triangle_points
from nightazimuth.aircraft_motion import AircraftPositionState


def test_triangle_tip_follows_requested_direction():
    points = _triangle_points(100.0, 50.0, 10.0, (1.0, 0.0))

    tip_x, tip_y = points[0], points[1]
    assert tip_x == 110.0
    assert tip_y == 50.0


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
