from dataclasses import replace

from nightazimuth.hud_finder_view import (
    apparent_angular_speed_deg_s,
    pan_live_view_window,
    select_finder_satellites,
)
from nightazimuth.sky_map import SkySatellite
from nightazimuth.track_prediction import TrackPoint


def _satellite(
    norad_id: str,
    *,
    elevation: float,
    range_km: float,
    visible: bool = True,
) -> SkySatellite:
    return SkySatellite(
        name=f"SAT-{norad_id}",
        norad_id=norad_id,
        azimuth_deg=180.0,
        elevation_deg=elevation,
        range_km=range_km,
        satellite_sunlit=visible,
        sky_dark=True,
        potentially_visible=visible,
    )


def _with_track(satellite: SkySatellite, *, azimuth_change: float, seconds: int = 20) -> SkySatellite:
    return replace(
        satellite,
        future_track=(
            TrackPoint(0, satellite.azimuth_deg, satellite.elevation_deg),
            TrackPoint(seconds, satellite.azimuth_deg + azimuth_change, satellite.elevation_deg),
        ),
    )


def test_default_finder_returns_small_fast_mover_set() -> None:
    satellites = [_satellite(str(index), elevation=10.0 + index, range_km=500.0 + index) for index in range(10)]

    chosen = select_finder_satellites(satellites)

    assert len(chosen) == 6


def test_finder_prefers_faster_apparent_motion() -> None:
    slow = _with_track(_satellite("slow", elevation=70.0, range_km=400.0), azimuth_change=2.0)
    fast = _with_track(_satellite("fast", elevation=25.0, range_km=1200.0), azimuth_change=20.0)

    chosen = select_finder_satellites([slow, fast], limit=1)

    assert [satellite.norad_id for satellite in chosen] == ["fast"]
    assert apparent_angular_speed_deg_s(fast) > apparent_angular_speed_deg_s(slow)


def test_sparse_finder_limits_and_ranks_candidates_without_tracks() -> None:
    satellites = [
        _satellite("1", elevation=20.0, range_km=500.0),
        _satellite("2", elevation=50.0, range_km=1200.0),
        _satellite("3", elevation=50.0, range_km=600.0),
        _satellite("4", elevation=10.0, range_km=100.0),
    ]

    chosen = select_finder_satellites(satellites, limit=3)

    assert [satellite.norad_id for satellite in chosen] == ["3", "2", "1"]


def test_sparse_finder_keeps_selected_object_even_when_not_potentially_visible() -> None:
    satellites = [
        _satellite("1", elevation=70.0, range_km=500.0),
        _satellite("2", elevation=60.0, range_km=600.0),
        _satellite("9", elevation=15.0, range_km=4000.0, visible=False),
    ]

    chosen = select_finder_satellites(satellites, selected_norad="9", limit=2)

    assert [satellite.norad_id for satellite in chosen] == ["1", "2", "9"]


def test_sparse_finder_has_no_hard_range_cutoff() -> None:
    satellites = [
        _satellite("far", elevation=80.0, range_km=30000.0),
        _satellite("near", elevation=20.0, range_km=500.0),
    ]

    chosen = select_finder_satellites(satellites, limit=1)

    assert [satellite.norad_id for satellite in chosen] == ["far"]


def test_show_all_returns_all_potentially_visible_candidates() -> None:
    satellites = [
        _satellite("1", elevation=20.0, range_km=500.0),
        _satellite("2", elevation=30.0, range_km=600.0),
        _satellite("3", elevation=40.0, range_km=700.0, visible=False),
    ]

    chosen = select_finder_satellites(satellites, show_all=True)

    assert [satellite.norad_id for satellite in chosen] == ["1", "2"]


def test_pan_can_reach_zenith_without_exceeding_90_degrees() -> None:
    facing, minimum, maximum = pan_live_view_window(
        facing_deg=180.0,
        minimum_elevation_deg=20.0,
        maximum_elevation_deg=70.0,
        horizontal_fov_deg=90.0,
        delta_x_fraction=0.0,
        delta_y_fraction=0.8,
    )

    assert facing == 180.0
    assert maximum == 90.0
    assert minimum == 40.0


def test_pan_wraps_azimuth_across_north() -> None:
    facing, minimum, maximum = pan_live_view_window(
        facing_deg=10.0,
        minimum_elevation_deg=0.0,
        maximum_elevation_deg=45.0,
        horizontal_fov_deg=90.0,
        delta_x_fraction=0.25,
        delta_y_fraction=0.0,
    )

    assert facing == 347.5
    assert minimum == 0.0
    assert maximum == 45.0
