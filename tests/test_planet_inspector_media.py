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
