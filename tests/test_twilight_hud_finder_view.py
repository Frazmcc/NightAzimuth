from nightazimuth.sky_map import SkySatellite
from nightazimuth.twilight_hud_finder_view import (
    is_live_observing_candidate,
    live_view_background_for_sky_state,
    select_twilight_finder_satellites,
)


def _satellite(
    norad_id: str,
    *,
    potential: bool = False,
    twilight: bool = False,
    sunlit: bool = True,
    elevation: float = 45.0,
    range_km: float = 1000.0,
) -> SkySatellite:
    return SkySatellite(
        name=f"SAT-{norad_id}",
        norad_id=norad_id,
        azimuth_deg=180.0,
        elevation_deg=elevation,
        range_km=range_km,
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


def test_finder_keeps_real_tracked_fallback_when_no_observing_candidate_exists() -> None:
    satellites = [
        _satellite("low", sunlit=False, elevation=12.0, range_km=900.0),
        _satellite("high", sunlit=False, elevation=61.0, range_km=1300.0),
    ]

    chosen = select_twilight_finder_satellites(satellites)

    assert len(chosen) == 1
    assert chosen[0].norad_id == "high"


def test_finder_never_invents_fallback_when_no_satellites_are_tracked() -> None:
    assert select_twilight_finder_satellites([]) == []


def test_live_view_background_darkens_with_solar_state() -> None:
    assert live_view_background_for_sky_state(4) == "#35566f"
    assert live_view_background_for_sky_state(3) == "#2a3a5b"
    assert live_view_background_for_sky_state(2) == "#182645"
    assert live_view_background_for_sky_state(1) == "#10182f"
    assert live_view_background_for_sky_state(0) == "#08111f"


def test_unknown_sky_state_uses_dark_background() -> None:
    assert live_view_background_for_sky_state(99) == "#08111f"
