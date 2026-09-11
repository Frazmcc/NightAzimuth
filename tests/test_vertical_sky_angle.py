from nightazimuth.gui_stage12 import vertical_sky_window


def test_zero_degrees_is_facing_horizon() -> None:
    window = vertical_sky_window(0.0, base_facing_deg=270.0)

    assert window.sky_angle_deg == 0.0
    assert window.facing_deg == 270.0
    assert window.minimum_elevation_deg == 0.0
    assert window.maximum_elevation_deg == 60.0


def test_ninety_degrees_is_zenith_window() -> None:
    window = vertical_sky_window(90.0, base_facing_deg=270.0)

    assert window.sky_angle_deg == 90.0
    assert window.facing_deg == 270.0
    assert window.minimum_elevation_deg == 30.0
    assert window.maximum_elevation_deg == 90.0


def test_180_degrees_is_opposite_horizon() -> None:
    window = vertical_sky_window(180.0, base_facing_deg=270.0)

    assert window.sky_angle_deg == 180.0
    assert window.facing_deg == 90.0
    assert window.minimum_elevation_deg == 0.0
    assert window.maximum_elevation_deg == 60.0


def test_sky_angle_is_clamped_to_valid_range() -> None:
    low = vertical_sky_window(-10.0, base_facing_deg=0.0)
    high = vertical_sky_window(200.0, base_facing_deg=0.0)

    assert low.sky_angle_deg == 0.0
    assert high.sky_angle_deg == 180.0
