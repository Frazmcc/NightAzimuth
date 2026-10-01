from pathlib import Path


SATELLITE_JS = Path("web/satellite-motion.js").read_text(encoding="utf-8")
HTML = Path("web/index.html").read_text(encoding="utf-8")


def test_satellites_use_small_point_source_markers() -> None:
    assert "function satelliteMarkerRadius" in SATELLITE_JS
    assert "const radius=2.45-.70*t" in SATELLITE_JS
    assert 'satelliteCtx.arc(x,y,radius,0,Math.PI*2)' in SATELLITE_JS
    assert "lineTo(x+5,y)" not in SATELLITE_JS
    assert "lineTo(x-5,y)" not in SATELLITE_JS


def test_satellites_use_independent_transparent_animation_canvas() -> None:
    assert 'satelliteCanvas.id="satellite-canvas"' in SATELLITE_JS
    assert 'skyCanvas.insertAdjacentElement("afterend",satelliteCanvas)' in SATELLITE_JS
    assert 'pointerEvents:"none"' in SATELLITE_JS
    assert "satelliteCtx.clearRect(0,0,w,h)" in SATELLITE_JS
    assert "layers.satellites=false" in SATELLITE_JS


def test_satellite_animation_does_not_repaint_whole_sky_each_frame() -> None:
    start = SATELLITE_JS.index("function animate(now){")
    end = SATELLITE_JS.index("// Clear any legacy diamond", start)
    animate_body = SATELLITE_JS[start:end]
    assert "drawSatelliteLayer()" in animate_body
    assert "requestAnimationFrame(animate)" in animate_body
    assert "drawSky()" not in animate_body
    assert "const FRAME_INTERVAL_MS=33" in SATELLITE_JS


def test_satellite_status_colours_are_semantic() -> None:
    assert 'label:"Recent launch",color:"#67d9ff"' in SATELLITE_JS
    assert 'label:"Active",color:"#79f2a6"' in SATELLITE_JS
    assert 'key:"junk",label:type,color:"#929ca5"' in SATELLITE_JS
    assert 'label:"Space station",color:"#f4fbff"' in SATELLITE_JS
    assert 'groups.has("LAST-30-DAYS")' in SATELLITE_JS
    assert 'groups.has("ACTIVE")' in SATELLITE_JS
    assert 'groups.has("STATIONS")' in SATELLITE_JS


def test_debris_and_rocket_bodies_are_classified_without_extra_requests() -> None:
    assert "function satelliteObjectType" in SATELLITE_JS
    assert "DEB(?:RIS)?" in SATELLITE_JS
    assert "R\\/B" in SATELLITE_JS
    assert "ROCKET BODY" in SATELLITE_JS
    assert "getJson(" not in SATELLITE_JS
    assert "fetch(" not in SATELLITE_JS


def test_satellite_selection_moves_detail_into_live_contacts() -> None:
    assert 'document.querySelector(".contacts-panel")' in SATELLITE_JS
    assert 'satelliteDetail.id="satellite-contact-detail"' in SATELLITE_JS
    assert 'contactsTitle.textContent="Satellite"' in SATELLITE_JS
    assert "renderSatelliteContacts" in SATELLITE_JS
    assert 'back.textContent="Back to aircraft"' in SATELLITE_JS
    for label in (
        "NORAD catalogue ID",
        "International designator",
        "Object type",
        "Slant range",
        "Angular speed",
        "Orbit class (derived)",
        "Perigee (derived)",
        "Apogee (derived)",
        "Element epoch",
        "Active catalogue",
        "Recent launch",
        "In 60 seconds",
    ):
        assert label in SATELLITE_JS


def test_selected_satellite_uses_real_projected_track_without_recentering() -> None:
    assert "skyXY(Number(satellite.azimuth_deg),Number(satellite.elevation_deg),w,h)" in SATELLITE_JS
    assert "function interpolateTrack" in SATELLITE_JS
    assert 'trackedObject?.kind==="satellite"' in SATELLITE_JS
    assert "originalUpdateTrackedView" in SATELLITE_JS
    assert 'if(typeof trackedObject!=="undefined"&&trackedObject?.kind==="satellite")return;' in SATELLITE_JS


def test_satellite_orbit_detail_is_derived_from_existing_payload() -> None:
    assert "const EARTH_MU_KM3_S2=398600.4418" in SATELLITE_JS
    assert "function derivedOrbit" in SATELLITE_JS
    assert "Math.cbrt" in SATELLITE_JS
    assert 'orbitClass="LEO"' in SATELLITE_JS
    assert 'orbitClass="MEO"' in SATELLITE_JS
    assert '?"GEO":"GSO"' in SATELLITE_JS


def test_satellite_renderer_asset_is_cache_busted() -> None:
    assert 'satellite-motion.js?v=21.11.18' in HTML
