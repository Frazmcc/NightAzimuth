from nightazimuth.stage20_perceptual_projection import project_perceptual_live_view


def test_view_centre_remains_centred() -> None:
    result = project_perceptual_live_view(270.0, 30.0, 270.0, 90.0)
    assert result.visible is True
    assert abs(result.x_fraction - 0.5) < 1.0e-9
    assert abs(result.y_fraction - 0.5) < 1.0e-9


def test_projection_is_left_right_symmetric() -> None:
    left = project_perceptual_live_view(240.0, 30.0, 270.0, 120.0)
    right = project_perceptual_live_view(300.0, 30.0, 270.0, 120.0)
    assert abs((left.x_fraction + right.x_fraction) - 1.0) < 1.0e-9
    assert abs(left.y_fraction - right.y_fraction) < 1.0e-9


def test_same_azimuth_bends_with_elevation_in_spherical_view() -> None:
    low = project_perceptual_live_view(300.0, 10.0, 270.0, 120.0)
    high = project_perceptual_live_view(300.0, 50.0, 270.0, 120.0)
    assert low.visible is True
    assert high.visible is True
    assert abs(low.x_fraction - high.x_fraction) > 0.05


def test_horizon_curves_across_wide_field() -> None:
    centre = project_perceptual_live_view(270.0, 0.0, 270.0, 120.0)
    edge = project_perceptual_live_view(320.0, 0.0, 270.0, 120.0)
    assert centre.visible is True
    assert edge.visible is True
    assert abs(edge.y_fraction - centre.y_fraction) > 0.01


def test_objects_outside_angular_field_remain_hidden() -> None:
    result = project_perceptual_live_view(350.0, 30.0, 270.0, 90.0)
    assert result.visible is False
