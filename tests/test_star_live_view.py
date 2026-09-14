from nightazimuth.star_live_view import (
    constellation_visual_style,
    is_vega_star,
    star_visual_style,
    vega_locator_text,
)
from nightazimuth.star_field import StarPoint


def test_vega_is_recognised_by_name() -> None:
    star = StarPoint(
        hip_id=91262,
        name="Vega",
        magnitude=0.03,
        azimuth_deg=180.0,
        elevation_deg=45.0,
    )

    assert is_vega_star(star)


def test_vega_gets_distinct_blue_white_style() -> None:
    star = StarPoint(
        hip_id=91262,
        name="Vega",
        magnitude=0.03,
        azimuth_deg=180.0,
        elevation_deg=45.0,
    )

    style = star_visual_style(star, selected=False)

    assert style.fill == "#dbeafe"
    assert style.label_fill == "#93c5fd"
    assert style.force_label is True
    assert style.radius > 3.5


def test_vega_locator_shows_live_azimuth_and_elevation() -> None:
    star = StarPoint(
        hip_id=91262,
        name="Vega",
        magnitude=0.03,
        azimuth_deg=287.4,
        elevation_deg=62.6,
    )

    assert vega_locator_text(star) == "VEGA  Az 287°  El 63°"


def test_constellation_auto_style_adapts_from_darkness_to_daylight() -> None:
    dark = constellation_visual_style(0)
    daylight = constellation_visual_style(4)

    assert dark.fill == "#64748b"
    assert dark.width == 1
    assert daylight.fill == "#102a3b"
    assert daylight.width == 2


def test_constellation_auto_style_boosts_contrast_for_cloud_overlay() -> None:
    clear = constellation_visual_style(2, cloud_overlay_enabled=False)
    cloud = constellation_visual_style(2, cloud_overlay_enabled=True)

    assert clear.fill == "#7dd3fc"
    assert clear.width == 2
    assert cloud.fill == "#e0f2fe"
    assert cloud.width == 3


def test_constellation_user_modes_override_automatic_strength() -> None:
    subtle = constellation_visual_style(3, cloud_overlay_enabled=True, contrast_mode="Subtle")
    strong = constellation_visual_style(3, contrast_mode="Strong")

    assert subtle.fill == "#6f8da8"
    assert subtle.width == 1
    assert strong.fill == "#f0f9ff"
    assert strong.width == 3


def test_constellation_unknown_mode_and_state_fall_back_safely() -> None:
    fallback = constellation_visual_style(99, contrast_mode="unknown")

    assert fallback == constellation_visual_style(4, contrast_mode="Auto")
