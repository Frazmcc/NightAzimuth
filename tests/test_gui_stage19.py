from nightazimuth.aircraft_live import SkyAircraft
from nightazimuth.aircraft_motion import AircraftPositionState
from nightazimuth.gui_stage19 import format_aircraft_detail


def test_aircraft_detail_exposes_state_age_source_and_aviation_units():
    aircraft = SkyAircraft(
        icao24="40621d",
        callsign="BAW123",
        azimuth_deg=231.8,
        elevation_deg=27.6,
        range_km=42.7,
        altitude_m=9448.8,
        track_deg=326.0,
        ground_speed_mps=230.47,
        vertical_rate_mps=3.2512,
        position_state=AircraftPositionState.EXTRAPOLATED,
        position_age_seconds=4.2,
        source_id="adsb-lol",
        source_label="adsb.lol",
    )

    text = format_aircraft_detail(aircraft)

    assert "BAW123" in text
    assert "ICAO: 40621D" in text
    assert "31,000 ft" in text
    assert "448 kt" in text
    assert "+640 ft/min" in text
    assert "Position: extrapolated" in text
    assert "Position age: 4.2 s" in text
    assert "Source: adsb.lol" in text
