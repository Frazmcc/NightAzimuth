from nightazimuth.stage20_human_vision import (
    apparent_star_magnitude,
    atmospheric_extinction_magnitude,
    night_colour_mix,
    sky_limiting_magnitude,
    star_visible_to_adapted_eye,
)


def test_dark_sky_allows_fainter_stars_than_twilight() -> None:
    assert sky_limiting_magnitude(0) > sky_limiting_magnitude(2)
    assert sky_limiting_magnitude(2) > sky_limiting_magnitude(3)
    assert sky_limiting_magnitude(3) > sky_limiting_magnitude(4)


def test_horizon_extinction_is_stronger_than_zenith() -> None:
    assert atmospheric_extinction_magnitude(5.0) > atmospheric_extinction_magnitude(60.0)
    assert atmospheric_extinction_magnitude(60.0) >= atmospheric_extinction_magnitude(90.0)


def test_same_star_can_be_visible_high_but_lost_near_horizon() -> None:
    magnitude = 5.0
    assert star_visible_to_adapted_eye(magnitude, 80.0, 0) is True
    assert star_visible_to_adapted_eye(magnitude, 3.0, 0) is False


def test_daylight_hides_ordinary_bright_stars() -> None:
    assert star_visible_to_adapted_eye(-1.46, 60.0, 4) is False


def test_extinction_only_makes_star_fainter() -> None:
    assert apparent_star_magnitude(2.0, 10.0) > 2.0


def test_dark_state_reduces_colour_more_than_daylight() -> None:
    assert night_colour_mix(0) > night_colour_mix(2) > night_colour_mix(4)
