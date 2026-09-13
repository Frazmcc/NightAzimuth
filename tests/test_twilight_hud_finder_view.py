from nightazimuth.sky_map import SkySatellite
from nightazimuth.twilight_hud_finder_view import (
    is_live_observing_candidate,
    select_twilight_finder_satellites,
)


def _satellite(
    norad_id: str,
    *,
    potential: bool = False,
    twilight: bool = False,
    sunlit: bool = True,
) -> SkySatellite:
    return SkySatellite(
        name=f"SAT-{norad_id}",
        norad_id=norad_id,
        azimuth_deg=180.0,
        elevation_deg=45.0,
        range_km=1000.0,
        satellite_sunlit=sunlit,
        sky_dark=potential,
        potentially_visible=potential,
        twilight_candidate=twilight,
    )


def test_twilight_satellite_is_live_candidate_before_dark_sky() -> None:
    satellite = _satellite("1", twilight=True)
    assert is_live_observing_candidate(satellite)


def test_shadowed_non_potential_satellite_is_not_live_candidate() -> None:
    satellite = _satellite("2", twilight=False, sunlit=False)
    assert not is_live_observing_candidate(satellite)


def test_finder_includes_dark_and_twilight_candidates() -> None:
    satellites = [
        _satellite("dark", potential=True),
        _satellite("twilight", twilight=True),
        _satellite("hidden", sunlit=False),
    ]

    chosen = select_twilight_finder_satellites(satellites, show_all=True)

    assert [satellite.norad_id for satellite in chosen] == ["dark", "twilight"]
