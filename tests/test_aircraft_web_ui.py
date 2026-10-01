from datetime import UTC, datetime
from pathlib import Path

from nightazimuth.aircraft_adsb_lol import _normalise_record


HTML = Path("web/index.html").read_text(encoding="utf-8")
CONTACTS_JS = Path("web/live-contacts-view.js").read_text(encoding="utf-8")
PERSPECTIVE_JS = Path("web/aircraft-perspective.js").read_text(encoding="utf-8")
LAYERS_JS = Path("web/layer-defaults.js").read_text(encoding="utf-8")


def test_adsb_navigation_selections_are_normalised() -> None:
    observation = _normalise_record(
        {
            "hex": "4ca123",
            "lat": 55.9,
            "lon": -4.4,
            "seen_pos": 1,
            "seen": 1,
            "alt_baro": 9000,
            "nav_altitude_mcp": 10000,
            "nav_altitude_fms": 12000,
            "nav_heading": 325,
        },
        datetime(2026, 10, 1, tzinfo=UTC),
        source_id="test",
        source_label="Test",
    )

    assert observation is not None
    assert observation.selected_altitude_ft == 10000
    assert observation.selected_heading_deg == 325


def test_adsb_attitude_fields_are_normalised_for_perspective_rendering() -> None:
    observation = _normalise_record(
        {
            "hex": "4ca125",
            "lat": 55.9,
            "lon": -4.4,
            "seen_pos": 1,
            "seen": 1,
            "alt_baro": 15700,
            "track": 324.67,
            "true_heading": 326.1,
            "mag_heading": 328.4,
            "track_rate": 0.12,
            "roll": 1.1,
        },
        datetime(2026, 10, 1, tzinfo=UTC),
        source_id="test",
        source_label="Test",
    )

    assert observation is not None
    assert observation.track_deg == 324.67
    assert observation.true_heading_deg == 326.1
    assert observation.magnetic_heading_deg == 328.4
    assert observation.track_rate_deg_s == 0.12
    assert observation.roll_deg == 1.1


def test_fms_altitude_is_used_when_mcp_altitude_is_missing() -> None:
    observation = _normalise_record(
        {
            "hex": "4ca124",
            "lat": 55.9,
            "lon": -4.4,
            "seen_pos": 1,
            "seen": 1,
            "alt_baro": 9000,
            "nav_altitude_fms": 14000,
        },
        datetime(2026, 10, 1, tzinfo=UTC),
        source_id="test",
        source_label="Test",
    )

    assert observation is not None
    assert observation.selected_altitude_ft == 14000


def test_aircraft_selection_does_not_recentre_live_sky() -> None:
    assert "function selectAircraftWithoutRecentering" in CONTACTS_JS
    assert 'if(trackedObject?.kind==="aircraft")return;' in CONTACTS_JS
    assert "focusAircraft=function(aircraft){selectAircraftWithoutRecentering(aircraft)}" in CONTACTS_JS
    assert "facing=Number(aircraft.azimuth_deg)" not in CONTACTS_JS
    assert "elevationCentre=clampElevationCentre(Number(aircraft.elevation_deg))" not in CONTACTS_JS


def test_selected_aircraft_details_match_observer_facing_layout() -> None:
    expected_labels = (
        "Aircraft type / model",
        "Operator / Airline",
        "Registration",
        "Callsign",
        "Distance",
        "Country of Registration",
        "AUTOPILOT / NAVIGATION",
        "Selected altitude",
        "Selected heading",
        "TRANSPONDER",
        "Squawk",
        "Squawk meaning",
        "Military",
        "PIA",
        "LADD",
        "FLIGHT",
        "Departure",
        "Arrival",
        "Route",
    )
    for label in expected_labels:
        assert label in CONTACTS_JS
    assert 'return raw.squawk_alert?.label||"Normal ATC assigned code"' in CONTACTS_JS
    assert "formatDistanceNm(raw.range_km)" in CONTACTS_JS


def test_aircraft_marker_style_is_configurable_and_cache_busted() -> None:
    assert 'id="aircraft-marker-style"' in HTML
    assert '<option value="silhouette" selected>Perspective aircraft</option>' in HTML
    assert '<option value="dot">Simple dots</option>' in HTML
    assert 'localStorage.getItem("nightazimuth.aircraftMarkerStyle")' in CONTACTS_JS
    assert "function drawSilhouettePath" in CONTACTS_JS
    assert "function markerSize" in CONTACTS_JS
    assert "live-contacts-view.js?v=21.11.25" in HTML


def test_perspective_aircraft_uses_real_attitude_and_world_track() -> None:
    for field in (
        "true_heading_deg",
        "magnetic_heading_deg",
        "track_rate_deg_s",
        "roll_deg",
        "future_track",
        "vertical_rate_mps",
        "ground_speed_mps",
    ):
        assert field in PERSPECTIVE_JS
    assert "function cameraBasis" in PERSPECTIVE_JS
    assert "function aircraftBasis" in PERSPECTIVE_JS
    assert "function projectLocal" in PERSPECTIVE_JS
    assert "shortestAngle(left.azimuth,right.azimuth)" in PERSPECTIVE_JS


def test_perspective_aircraft_depth_is_bounded_zero_to_fifty_miles() -> None:
    assert "const MAX_RANGE_MILES=50" in PERSPECTIVE_JS
    assert "const MIN_MODEL_SIZE=7.5" in PERSPECTIVE_JS
    assert "const MAX_MODEL_SIZE=24" in PERSPECTIVE_JS
    assert "const t=miles/MAX_RANGE_MILES" in PERSPECTIVE_JS
    assert "t*t*(3-2*t)" in PERSPECTIVE_JS
    assert ".sort((a,b)=>b.state.rangeKm-a.state.rangeKm)" in PERSPECTIVE_JS


def test_perspective_aircraft_reuses_single_aircraft_payload() -> None:
    assert "getJson(" not in PERSPECTIVE_JS
    assert "fetch(" not in PERSPECTIVE_JS
    assert 'perspective.src="./aircraft-perspective.js?v=22.3.3"' in LAYERS_JS
    assert 'layer-defaults.js?v=21.11.19' in HTML


def test_perspective_geometry_does_not_double_apply_depth_distortion() -> None:
    assert "return[originX+sx*size,originY+sy*size,depth]" in PERSPECTIVE_JS
    assert "const perspective=clamp(1/(1+depth*.12)" not in PERSPECTIVE_JS
    assert "function drawSurface" in PERSPECTIVE_JS
    assert "const rightWing=" in PERSPECTIVE_JS
    assert "const leftWing=" in PERSPECTIVE_JS
    assert "const nose=projectLocal([geometry.noseX,0,0]" in PERSPECTIVE_JS
    assert "tail=projectLocal([geometry.tailX,0,0]" in PERSPECTIVE_JS


def test_edge_on_aircraft_keep_a_readable_projected_shape() -> None:
    assert "const MIN_FORWARD_PROJECTION=.18" in PERSPECTIVE_JS
    assert "const MIN_LATERAL_PROJECTION=.34" in PERSPECTIVE_JS
    assert "const MIN_VERTICAL_PROJECTION=.16" in PERSPECTIVE_JS
    assert "function readableAxis" in PERSPECTIVE_JS
    assert "function projectionFrame" in PERSPECTIVE_JS
    assert "readableAxis(lateral,lateralFallback,MIN_LATERAL_PROJECTION)" in PERSPECTIVE_JS


def test_aircraft_visual_polish_is_type_aware_and_oriented() -> None:
    assert "function aircraftProfile" in PERSPECTIVE_JS
    for profile in ("widebody", "regional", "turboprop", "business", "narrowbody", "military"):
        assert profile in PERSPECTIVE_JS
    assert "function drawNavigationLights" in PERSPECTIVE_JS
    assert 'fill:"#ff5b66"' in PERSPECTIVE_JS
    assert 'fill:"#71ff9b"' in PERSPECTIVE_JS
    assert 'fill:"#f7fbff"' in PERSPECTIVE_JS


def test_aircraft_labels_follow_model_bounds_and_avoid_each_other() -> None:
    assert "function projectedBounds" in PERSPECTIVE_JS
    assert "function boxesOverlap" in PERSPECTIVE_JS
    assert "function drawAircraftLabels" in PERSPECTIVE_JS
    assert "label.bounds.maxX+8" in PERSPECTIVE_JS
    assert "labelBoxes.some(existing=>boxesOverlap(box,existing))" in PERSPECTIVE_JS


def test_coasting_aircraft_are_softened_without_stopping_animation() -> None:
    assert 'aircraft?.position_state==="coasting"' in PERSPECTIVE_JS
    assert 'aircraft?.continuity_state==="coasting"' in PERSPECTIVE_JS
    assert "const alpha=selected?1:(coasting ? .62 : 1)" in PERSPECTIVE_JS


def test_aircraft_animation_uses_independent_transparent_overlay() -> None:
    assert 'aircraftCanvas.id="aircraft-canvas"' in PERSPECTIVE_JS
    assert 'skyCanvas.insertAdjacentElement("afterend",aircraftCanvas)' in PERSPECTIVE_JS
    assert 'pointerEvents:"none"' in PERSPECTIVE_JS
    assert "const aircraftCtx=aircraftCanvas.getContext(\"2d\")" in PERSPECTIVE_JS
    assert "aircraftCtx.clearRect(0,0,w,h)" in PERSPECTIVE_JS
    assert "try{layers.aircraft=false;baseDrawContacts(w,h)}finally{layers.aircraft=previous}" in PERSPECTIVE_JS


def test_aircraft_animation_does_not_repaint_the_whole_sky() -> None:
    animate_start = PERSPECTIVE_JS.index("function animate(){")
    animate_end = PERSPECTIVE_JS.index("skyCanvas.addEventListener", animate_start)
    animate_body = PERSPECTIVE_JS[animate_start:animate_end]
    assert "drawPerspectiveLayer()" in animate_body
    assert "drawSky();" not in animate_body
    assert "requestAnimationFrame(animate)" in animate_body
    assert "const MAX_PREDICTION_SECONDS=15" in PERSPECTIVE_JS
    assert "if(!document.hidden&&perspectiveEnabled()" in animate_body


def test_fresh_provider_snapshots_are_eased_without_position_snaps() -> None:
    assert "const HANDOFF_SECONDS=.45" in PERSPECTIVE_JS
    assert "function blendState" in PERSPECTIVE_JS
    assert "handoffFrom:previous" in PERSPECTIVE_JS
    assert "elapsed/HANDOFF_SECONDS" in PERSPECTIVE_JS
    assert "shortestAngle(from.azimuth,to.azimuth)" in PERSPECTIVE_JS
    assert "shortestAngle(from.heading,to.heading)" in PERSPECTIVE_JS


def test_aircraft_overlay_keeps_selection_clicks_on_main_canvas() -> None:
    assert 'skyCanvas.addEventListener("click",event=>' in PERSPECTIVE_JS
    assert "for(const target of aircraftHits)" in PERSPECTIVE_JS
    assert "event.stopImmediatePropagation()" in PERSPECTIVE_JS
    assert "toggleTracking(best)" in PERSPECTIVE_JS
    assert "{capture:true}" in PERSPECTIVE_JS


def test_live_contacts_are_humanised() -> None:
    assert "formatDistanceNm(aircraft.range_km)" in CONTACTS_JS
    assert "formatAltitudeFeet(aircraft.altitude_m)" in CONTACTS_JS
    assert "verticalState(aircraft.vertical_rate_mps)" in CONTACTS_JS
    assert 'aircraft.operator?`${aircraft.operator} · ${callsign}`:callsign' in CONTACTS_JS
