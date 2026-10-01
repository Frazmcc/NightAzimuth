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
    assert 'perspective.src="./aircraft-perspective.js?v=22.3.0"' in LAYERS_JS
    assert 'layer-defaults.js?v=21.11.16' in HTML


def test_perspective_aircraft_animation_is_bounded_and_pauses_when_hidden() -> None:
    assert "const ANIMATION_INTERVAL_MS=100" in PERSPECTIVE_JS
    assert "const MAX_PREDICTION_SECONDS=15" in PERSPECTIVE_JS
    assert "if(!document.hidden&&perspectiveEnabled()" in PERSPECTIVE_JS
    assert "requestAnimationFrame(animate)" in PERSPECTIVE_JS


def test_live_contacts_are_humanised() -> None:
    assert "formatDistanceNm(aircraft.range_km)" in CONTACTS_JS
    assert "formatAltitudeFeet(aircraft.altitude_m)" in CONTACTS_JS
    assert "verticalState(aircraft.vertical_rate_mps)" in CONTACTS_JS
    assert 'aircraft.operator?`${aircraft.operator} · ${callsign}`:callsign' in CONTACTS_JS
