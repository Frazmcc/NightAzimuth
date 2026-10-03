import re
from pathlib import Path

HTML = Path("web/index.html").read_text(encoding="utf-8")
CSS = Path("web/styles.css").read_text(encoding="utf-8")
APP = Path("web/app.js").read_text(encoding="utf-8")


def test_planet_inspector_has_optional_real_image_media_slot() -> None:
    assert 'id="inspector-media"' in HTML
    assert 'id="inspector-image"' in HTML
    assert 'id="inspector-image-credit"' in HTML
    assert 'id="inspector-media-link"' in HTML
    assert ".inspector-media[hidden]{display:none}" in CSS
    assert "object-fit:contain" in CSS


def test_planet_inspector_has_real_spacecraft_image_catalogue() -> None:
    assert "const PLANET_MEDIA=" in APP
    for planet in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"):
        assert f"{planet}:" in APP
    assert "MESSENGER" in APP
    assert "Mariner 10" in APP
    assert "Rosetta OSIRIS" in APP
    assert "Cassini" in APP
    assert "Voyager 2" in APP
    assert "Special:FilePath" in APP


def test_non_planet_objects_hide_planet_media_and_failed_images_fail_closed() -> None:
    assert 'target.kind==="planet"?PLANET_MEDIA[item.name]:null' in APP
    assert "if(!media)return;" in APP
    assert 'if(generation===inspectorMediaGeneration){mediaRoot.hidden=true;image.removeAttribute("src")}' in APP
    assert "updateInspectorMedia(target,item)" in APP


def test_star_points_expose_equatorial_coordinates_for_real_survey_images() -> None:
    star_field = Path("src/nightazimuth/star_field.py").read_text(encoding="utf-8")
    assert "ra_deg: float | None = None" in star_field
    assert "dec_deg: float | None = None" in star_field
    assert 'ra_deg=float(self._catalogue.at[hip_id, "ra_degrees"])' in star_field
    assert 'dec_deg=float(self._catalogue.at[hip_id, "dec_degrees"])' in star_field


def test_star_inspector_uses_real_dss2_survey_imagery_when_coordinates_exist() -> None:
    assert 'target.kind==="star"&&item.hip_id!=null' in APP
    assert 'hips:"CDS/P/DSS2/color"' in APP
    assert 'width:"500",height:"300"' in APP
    assert 'params.object="HIP "+item.hip_id' in APP
    assert 'https://alasky.cds.unistra.fr/hips-image-services/hips2fits?' in APP
    assert 'Real sky-survey image · DSS2 / CDS' in APP
    assert 'Number.isFinite(Number(item.ra_deg))' in APP
    assert 'Number.isFinite(Number(item.dec_deg))' in APP


def test_csp_allows_planet_and_star_image_sources() -> None:
    csp_match = re.search(
        r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">',
        HTML,
    )
    assert csp_match is not None
    directives = {
        parts[0]: parts[1:]
        for directive in csp_match.group(1).split(";")
        if (parts := directive.strip().split())
    }
    assert directives["img-src"] == [
        "'self'",
        "data:",
        "https://upload.wikimedia.org",
        "https://commons.wikimedia.org",
        "https://alasky.cds.unistra.fr",
        "https://cdn.planespotters.net",
        "https://images.planespotters.net",
    ]


def test_planet_and_star_inspector_has_facts_section_below_media() -> None:
    media_pos = HTML.index('id="inspector-media"')
    facts_pos = HTML.index('id="inspector-facts"')
    type_pos = HTML.index('id="inspector-type"')
    assert media_pos < facts_pos < type_pos
    assert 'id="inspector-facts-list"' in HTML
    assert "const PLANET_FACTS=" in APP
    for body in ("Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"):
        assert f"{body}:[" in APP


def test_star_facts_are_catalogue_specific_and_not_placeholder_copy() -> None:
    assert "function starFacts(item)" in APP
    assert "Hipparcos catalogue identifier" in APP
    assert "Apparent magnitude" in APP
    assert "right ascension" in APP
    assert "Astrometry: ESA Hipparcos catalogue" in APP
    assert "function updateInspectorFacts(target,item)" in APP
    assert "updateInspectorFacts(target,item)" in APP


def test_star_payload_exposes_distance_and_motion_facts() -> None:
    star_field = Path("src/nightazimuth/star_field.py").read_text(encoding="utf-8")
    assert "parallax_mas: float | None = None" in star_field
    assert "distance_pc: float | None = None" in star_field
    assert "distance_ly: float | None = None" in star_field
    assert "absolute_magnitude: float | None = None" in star_field
    assert "proper_motion_mas_per_year: float | None = None" in star_field
    assert "1000.0 / parallax_mas" in star_field
    assert "distance_pc * 3.26156" in star_field


def test_planet_payload_exposes_current_distance_and_light_time() -> None:
    star_field = Path("src/nightazimuth/star_field.py").read_text(encoding="utf-8")
    assert "distance_from_observer_km: float | None = None" in star_field
    assert "distance_from_observer_au: float | None = None" in star_field
    assert "light_time_minutes: float | None = None" in star_field
    assert "planet_distance.km" in star_field
    assert "planet_distance.au" in star_field


def test_facts_include_physical_orbital_and_notable_information() -> None:
    assert "Size:" in APP
    assert "Average distance from the Sun:" in APP
    assert "Composition:" in APP
    assert "Atmosphere:" in APP
    assert "Temperature:" in APP
    assert "Current distance from your observing position:" in APP
    assert "STAR_NOTABLE_FACTS" in APP
    assert "Age:" in APP
    assert "Theta Draconis" in APP
    assert "spectroscopic binary" in APP
    assert "Great Dimming" in APP
