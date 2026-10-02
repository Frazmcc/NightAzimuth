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
    assert 'if(!media){mediaRoot.hidden=true;image.removeAttribute("src");image.alt="";return}' in APP
    assert 'image.onerror=()=>{mediaRoot.hidden=true;image.removeAttribute("src")}' in APP
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
    ]
