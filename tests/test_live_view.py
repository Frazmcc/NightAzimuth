from nightazimuth.live_view import project_live_view, signed_angular_difference


def test_signed_angular_difference_wraps_across_north() -> None:
    assert signed_angular_difference(5.0, 355.0) == 10.0
    assert signed_angular_difference(355.0, 5.0) == -10.0


def test_object_at_facing_direction_and_30_degrees_is_centred() -> None:
    result = project_live_view(270.0, 30.0, 270.0, 90.0)
    assert result.visible is True
    assert result.x_fraction == 0.5
    assert result.y_fraction == 0.5


def test_45_degrees_uses_practical_0_to_60_vertical_scale() -> None:
    result = project_live_view(270.0, 45.0, 270.0, 90.0)
    assert result.visible is True
    assert result.x_fraction == 0.5
    assert result.y_fraction == 0.25


def test_object_above_practical_60_degree_limit_is_hidden() -> None:
    result = project_live_view(270.0, 70.0, 270.0, 90.0)
    assert result.visible is False


def test_object_outside_horizontal_field_of_view_is_hidden() -> None:
    result = project_live_view(100.0, 30.0, 0.0, 90.0)
    assert result.visible is False


def test_north_wrap_remains_visible() -> None:
    result = project_live_view(5.0, 20.0, 355.0, 30.0)
    assert result.visible is True


def test_zoomed_vertical_window_projects_relative_to_window() -> None:
    result = project_live_view(
        270.0,
        30.0,
        270.0,
        45.0,
        minimum_elevation_deg=20.0,
        maximum_elevation_deg=40.0,
    )
    assert result.visible is True
    assert result.x_fraction == 0.5
    assert result.y_fraction == 0.5
