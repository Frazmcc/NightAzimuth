from math import isclose

from nightazimuth.sky_map import project_sky_position


def test_zenith_projects_to_centre() -> None:
    x, y = project_sky_position(123.0, 90.0, center_x=100.0, center_y=100.0, radius=80.0)
    assert isclose(x, 100.0, abs_tol=1e-9)
    assert isclose(y, 100.0, abs_tol=1e-9)


def test_horizon_cardinal_directions() -> None:
    north = project_sky_position(0.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)
    east = project_sky_position(90.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)
    south = project_sky_position(180.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)
    west = project_sky_position(270.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)

    assert isclose(north[0], 100.0, abs_tol=1e-9)
    assert isclose(north[1], 20.0, abs_tol=1e-9)
    assert isclose(east[0], 180.0, abs_tol=1e-9)
    assert isclose(east[1], 100.0, abs_tol=1e-9)
    assert isclose(south[0], 100.0, abs_tol=1e-9)
    assert isclose(south[1], 180.0, abs_tol=1e-9)
    assert isclose(west[0], 20.0, abs_tol=1e-9)
    assert isclose(west[1], 100.0, abs_tol=1e-9)


def test_mid_elevation_uses_half_radius() -> None:
    x, y = project_sky_position(90.0, 45.0, center_x=100.0, center_y=100.0, radius=80.0)
    assert isclose(x, 140.0, abs_tol=1e-9)
    assert isclose(y, 100.0, abs_tol=1e-9)
