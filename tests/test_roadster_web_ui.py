from pathlib import Path


ROADSTER_JS = Path("web/roadster-deep-space.js").read_text(encoding="utf-8")
HTML = Path("web/index.html").read_text(encoding="utf-8")
CSS = Path("web/styles.css").read_text(encoding="utf-8")
CAMERA_JS = Path("web/camera-settings.js").read_text(encoding="utf-8")


def test_roadster_is_a_small_red_point_in_the_stars_layer() -> None:
    assert 'const ROADSTER_RED="#d72b35"' in ROADSTER_JS
    assert 'layers.stars===false' in ROADSTER_JS
    assert "skyXY(az,el,w,h)" in ROADSTER_JS
    assert "ctx.arc(x,y,radius,0,Math.PI*2)" in ROADSTER_JS
    assert "radius=selected?4.2:2.8" in ROADSTER_JS
    assert 'ctx.fillText("TESLA ROADSTER"' in ROADSTER_JS
    assert "r:12" in ROADSTER_JS


def test_roadster_comes_from_sky_payload_without_polluting_star_catalogue() -> None:
    assert "celestialSky?.deep_space_objects" in ROADSTER_JS
    assert "celestialSky.stars" not in ROADSTER_JS
    assert "deep_space_objects" not in CAMERA_JS
    assert "getJson(" not in ROADSTER_JS
    assert "fetch(" not in ROADSTER_JS
    assert "ssd.jpl.nasa.gov" not in ROADSTER_JS


def test_roadster_click_opens_relevant_live_contacts_detail() -> None:
    assert 'contactsTitle.textContent="Deep Space"' in ROADSTER_JS
    assert 'roadsterDetail.id="roadster-contact-detail"' in ROADSTER_JS
    assert 'trackedObject={kind:"deep_space",key}' in ROADSTER_JS
    for label in (
        "International designator",
        "JPL Horizons target",
        "Launch date",
        "Launch vehicle",
        "Payload",
        "Body colour",
        "Azimuth",
        "Elevation",
        "Right ascension",
        "Declination",
        "Constellation",
        "Distance from Earth",
        "Distance from Sun",
        "Earth range rate",
        "Heliocentric speed",
        "Observer-relative speed",
        "One-way light time",
        "Solar elongation",
        "Phase angle",
        "Ephemeris time",
        "Data source",
    ):
        assert label in ROADSTER_JS
    assert "no live telemetry is received from the Roadster" in ROADSTER_JS


def test_roadster_media_is_historical_public_domain_and_not_presented_as_live() -> None:
    assert "upload.wikimedia.org" in ROADSTER_JS
    assert "Historical SpaceX onboard view" in ROADSTER_JS
    assert "CC0/public domain" in ROADSTER_JS
    assert "not live" in ROADSTER_JS
    assert "roadster-media-drift" in CSS
    assert "prefers-reduced-motion:reduce" in CSS
    assert "img-src 'self' data: https://upload.wikimedia.org" in HTML


def test_roadster_assets_are_loaded_in_safe_order_and_cache_busted() -> None:
    assert './styles.css?v=21.11.1' in HTML
    roadster = HTML.index('roadster-deep-space.js?v=21.11.1')
    layout = HTML.index('live-sky-layout.js?v=21.11.24')
    satellites = HTML.index('satellite-motion.js?v=21.11.18')
    assert layout < roadster < satellites


def test_roadster_selection_does_not_recentre_live_sky() -> None:
    select_start = ROADSTER_JS.index("function selectRoadster")
    select_end = ROADSTER_JS.index("function drawRoadster", select_start)
    select_body = ROADSTER_JS[select_start:select_end]
    assert "facing=" not in select_body
    assert "elevationCentre=" not in select_body
