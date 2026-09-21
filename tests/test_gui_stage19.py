from nightazimuth.aircraft_live import SkyAircraft
from nightazimuth.aircraft_motion import AircraftPositionState
from nightazimuth.aircraft_squawk import classify_squawk
from nightazimuth.gui_stage19 import format_aircraft_detail


def _aircraft(*, squawk: str | None = None, military: bool = False) -> SkyAircraft:
    return SkyAircraft(
        icao24="40621d",
        callsign="BAW123" if not military else "RCH123",
        azimuth_deg=231.8,
        elevation_deg=27.6,
        range_km=42.7,
        altitude_m=9448.8,
        track_deg=326.0,
        ground_speed_mps=230.47,
        vertical_rate_mps=3.2512,
        squawk=squawk,
        squawk_alert=classify_squawk(squawk),
        position_state=AircraftPositionState.EXTRAPOLATED,
        position_age_seconds=4.2,
        source_id="adsb-lol",
        source_label="adsb.lol",
        registration="62-3565" if military else None,
        type_code="K35R" if military else None,
        type_description="BOEING KC-135R STRATOTANKER" if military else None,
        operator="UNITED STATES AIR FORCE" if military else None,
        military=military,
    )


def test_aircraft_detail_exposes_state_age_source_and_aviation_units():
    text = format_aircraft_detail(_aircraft())
    assert "BAW123" in text
    assert "ICAO: 40621D" in text
    assert "31,000 ft" in text
    assert "448 kt" in text
    assert "+640 ft/min" in text
    assert "Position: extrapolated" in text
    assert "Position age: 4.2 s" in text
    assert "Source: adsb.lol" in text


def test_aircraft_detail_leads_with_special_squawk_alert():
    text = format_aircraft_detail(_aircraft(squawk="0023"))
    assert text.startswith("⚠ SEARCH & RESCUE\nSquawk: 0023")


def test_military_aircraft_detail_exposes_type_operator_and_registration():
    text = format_aircraft_detail(_aircraft(military=True))
    assert "MILITARY" in text
    assert "Aircraft: BOEING KC-135R STRATOTANKER" in text
    assert "ICAO type: K35R" in text
    assert "Operator: UNITED STATES AIR FORCE" in text
    assert "Registration: 62-3565" in text
