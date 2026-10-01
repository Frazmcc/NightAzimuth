from datetime import UTC, datetime
from pathlib import Path

from nightazimuth.aircraft_adsb_lol import _normalise_record


HTML = Path("web/index.html").read_text(encoding="utf-8")
CONTACTS_JS = Path("web/live-contacts-view.js").read_text(encoding="utf-8")


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
    assert '<option value="silhouette" selected>Aircraft silhouettes</option>' in HTML
    assert '<option value="dot">Simple dots</option>' in HTML
    assert 'localStorage.getItem("nightazimuth.aircraftMarkerStyle")' in CONTACTS_JS
    assert "function drawSilhouettePath" in CONTACTS_JS
    assert "function markerSize" in CONTACTS_JS
    assert "live-contacts-view.js?v=21.11.25" in HTML


def test_live_contacts_are_humanised() -> None:
    assert "formatDistanceNm(aircraft.range_km)" in CONTACTS_JS
    assert "formatAltitudeFeet(aircraft.altitude_m)" in CONTACTS_JS
    assert "verticalState(aircraft.vertical_rate_mps)" in CONTACTS_JS
    assert 'aircraft.operator?`${aircraft.operator} · ${callsign}`:callsign' in CONTACTS_JS
