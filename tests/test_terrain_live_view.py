from nightazimuth.terrain_horizon import HorizonPoint
from nightazimuth.terrain_star_live_view import terrain_profile_for_view


def test_terrain_profile_projects_current_direction() -> None:
    horizon = (
        HorizonPoint(azimuth_deg=260.0, elevation_deg=4.0),
        HorizonPoint(azimuth_deg=270.0, elevation_deg=10.0),
        HorizonPoint(azimuth_deg=280.0, elevation_deg=6.0),
    )

    profile = terrain_profile_for_view(
        horizon,
        facing_deg=270.0,
        horizontal_fov_deg=40.0,
        minimum_elevation_deg=0.0,
        maximum_elevation_deg=60.0,
    )

    assert len(profile) == 3
    assert profile[1][0] == 0.5
    assert profile[1][1] < profile[0][1]


def test_terrain_profile_wraps_across_north() -> None:
    horizon = (
        HorizonPoint(azimuth_deg=350.0, elevation_deg=5.0),
        HorizonPoint(azimuth_deg=0.0, elevation_deg=8.0),
        HorizonPoint(azimuth_deg=10.0, elevation_deg=6.0),
        HorizonPoint(azimuth_deg=180.0, elevation_deg=30.0),
    )

    profile = terrain_profile_for_view(
        horizon,
        facing_deg=0.0,
        horizontal_fov_deg=30.0,
        minimum_elevation_deg=0.0,
        maximum_elevation_deg=60.0,
    )

    assert len(profile) == 3
    assert [round(point[0], 3) for point in profile] == [0.167, 0.5, 0.833]


def test_terrain_below_zoomed_vertical_window_clamps_to_bottom() -> None:
    profile = terrain_profile_for_view(
        (HorizonPoint(azimuth_deg=90.0, elevation_deg=5.0),),
        facing_deg=90.0,
        horizontal_fov_deg=30.0,
        minimum_elevation_deg=20.0,
        maximum_elevation_deg=40.0,
    )

    assert profile == ((0.5, 1.0),)
