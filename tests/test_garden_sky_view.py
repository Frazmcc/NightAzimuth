import math

from nightazimuth.garden_sky_view import project_garden_sky


def test_zenith_projects_to_centre() -> None:
    x, y = project_garden_sky(123.0, 90.0, center_x=100.0, center_y=100.0, radius=80.0)

    assert x == 100.0
    assert y == 100.0


def test_north_horizon_projects_to_top_edge() -> None:
    x, y = project_garden_sky(0.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)

    assert math.isclose(x, 100.0, abs_tol=1e-9)
    assert math.isclose(y, 20.0, abs_tol=1e-9)


def test_east_horizon_projects_to_right_edge() -> None:
    x, y = project_garden_sky(90.0, 0.0, center_x=100.0, center_y=100.0, radius=80.0)

    assert math.isclose(x, 180.0, abs_tol=1e-9)
    assert math.isclose(y, 100.0, abs_tol=1e-9)


def test_45_degree_elevation_is_halfway_to_zenith() -> None:
    x, y = project_garden_sky(180.0, 45.0, center_x=100.0, center_y=100.0, radius=80.0)

    assert math.isclose(x, 100.0, abs_tol=1e-9)
    assert math.isclose(y, 140.0, abs_tol=1e-9)
