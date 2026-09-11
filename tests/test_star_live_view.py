from nightazimuth.star_live_view import is_vega_star, star_visual_style, vega_locator_text
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
