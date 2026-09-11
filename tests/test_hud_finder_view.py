from nightazimuth.hud_finder_view import select_finder_satellites
from nightazimuth.sky_map import SkySatellite


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


def test_sparse_finder_limits_and_ranks_candidates() -> None:
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
