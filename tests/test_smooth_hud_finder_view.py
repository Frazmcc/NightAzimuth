from nightazimuth.sky_map import SkySatellite
from nightazimuth.smooth_hud_finder_view import interpolated_satellite_position
from nightazimuth.track_prediction import TrackPoint


def _satellite(track: tuple[TrackPoint, ...]) -> SkySatellite:
    return SkySatellite(
        name="TEST",
        norad_id="1",
        azimuth_deg=10.0,
        elevation_deg=20.0,
        range_km=500.0,
        satellite_sunlit=True,
        sky_dark=True,
        potentially_visible=True,
        future_track=track,
    )


def test_interpolates_between_one_second_track_points() -> None:
    satellite = _satellite(
        (
            TrackPoint(0, 100.0, 20.0),
            TrackPoint(1, 102.0, 22.0),
        )
    )

    azimuth, elevation = interpolated_satellite_position(satellite, 0.5)

    assert azimuth == 101.0
    assert elevation == 21.0


def test_interpolation_wraps_cleanly_across_north() -> None:
    satellite = _satellite(
        (
            TrackPoint(0, 359.0, 30.0),
            TrackPoint(1, 1.0, 30.0),
        )
    )

    azimuth, elevation = interpolated_satellite_position(satellite, 0.5)

    assert azimuth == 0.0
    assert elevation == 30.0


def test_position_clamps_to_last_track_point_after_track_window() -> None:
    satellite = _satellite(
        (
            TrackPoint(0, 10.0, 20.0),
            TrackPoint(1, 11.0, 21.0),
        )
    )

    assert interpolated_satellite_position(satellite, 5.0) == (11.0, 21.0)
