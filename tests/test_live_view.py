from nightazimuth.live_view import project_live_view, signed_angular_difference


def test_signed_angular_difference_wraps_across_north() -> None:
    assert signed_angular_difference(5.0, 355.0) == 10.0
    assert signed_angular_difference(355.0, 5.0) == -10.0


def test_object_at_facing_direction_is_centred() -> None:
    result = project_live_view(270.0, 45.0, 270.0, 90.0)
    assert result.visible is True
    assert result.x_fraction == 0.5
    assert result.y_fraction == 0.5


def test_object_outside_horizontal_field_of_view_is_hidden() -> None:
    result = project_live_view(100.0, 30.0, 0.0, 90.0)
    assert result.visible is False


def test_north_wrap_remains_visible() -> None:
    result = project_live_view(5.0, 20.0, 355.0, 30.0)
    assert result.visible is True
