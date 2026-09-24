from datetime import UTC, datetime

from nightazimuth.aircraft_display import aircraft_display_identity, squawk_display
from nightazimuth.aircraft_live import SkyAircraft
from nightazimuth.aircraft_motion import AircraftPositionState
from nightazimuth.aircraft_routes import AircraftRoute, AirportInfo
from nightazimuth.aircraft_squawk import classify_squawk
from nightazimuth.gui_stage20_clean import prioritise_aircraft_board
from nightazimuth.stage20_aircraft_detail import estimate_arrival_time, format_stage20_aircraft_detail


def _aircraft(
    *,
    icao24: str = "40621d",
    callsign: str = "TEST123",
    squawk: str | None = None,
    type_code: str = "A320",
    operator: str | None = "Example Air",
    military: bool = False,
    range_km: float = 20.0,
) -> SkyAircraft:
    return SkyAircraft(
        icao24=icao24,
        callsign=callsign,
        azimuth_deg=180.0,
        elevation_deg=25.0,
        range_km=range_km,
        altitude_m=10_000.0,
        track_deg=270.0,
        ground_speed_mps=220.0,
        vertical_rate_mps=0.0,
        squawk=squawk,
        squawk_alert=classify_squawk(squawk),
        position_state=AircraftPositionState.MEASURED,
        position_age_seconds=1.0,
        source_id="adsb_lol",
        source_label="ADSB.lol",
        registration="G-TEST",
        type_code=type_code,
        type_description=None,
        operator=operator,
        military=military,
        latitude_deg=51.47,
        longitude_deg=-0.45,
    )


def test_emergency_and_special_squawks_are_pinned_before_normal_contacts() -> None:
    normal = _aircraft(icao24="aaaaaa", callsign="NORMAL", range_km=1.0)
    sar = _aircraft(icao24="bbbbbb", callsign="RESCUE", squawk="0023", range_km=80.0)
    emergency = _aircraft(icao24="cccccc", callsign="MAYDAY", squawk="7700", range_km=120.0)

    ordered = prioritise_aircraft_board([normal, sar, emergency])

    assert [item.callsign for item in ordered] == ["MAYDAY", "RESCUE", "NORMAL"]


def test_squawk_display_keeps_code_and_adds_plain_english_description() -> None:
    aircraft = _aircraft(squawk="7600")
    assert squawk_display(aircraft) == "7600 — Radio failure"


def test_h135_air_ambulance_role_and_capacity_are_human_readable() -> None:
    aircraft = _aircraft(
        type_code="EC35",
        operator="Midlands Air Ambulance HEMS",
    )
    identity = aircraft_display_identity(aircraft)

    assert identity.make_model == "Airbus Helicopters H135 / EC135"
    assert identity.capacity == "typically 5–7 seats"
    assert identity.role == "Air Ambulance / HEMS"


def test_aw189_search_and_rescue_operator_is_labelled_coastguard_sar() -> None:
    aircraft = _aircraft(
        type_code="A189",
        operator="HM Coastguard Search and Rescue",
    )
    identity = aircraft_display_identity(aircraft)
    assert identity.make_model == "Leonardo AW189"
    assert identity.role == "Coastguard / Search & Rescue"


def test_eta_is_estimated_from_live_position_speed_and_arrival_coordinates() -> None:
    aircraft = _aircraft()
    arrival = AirportInfo(
        name="Glasgow Airport",
        icao="EGPF",
        iata="GLA",
        location="Glasgow",
        country_iso2="GB",
        latitude_deg=55.8719,
        longitude_deg=-4.4331,
    )
    now = datetime(2026, 9, 21, 17, 0, tzinfo=UTC)

    result = estimate_arrival_time(aircraft, arrival, now=now)

    assert result is not None
    eta, minutes = result
    assert eta > now
    assert 30 < minutes < 120


def test_detail_places_identity_squawk_and_journey_before_tracking_telemetry() -> None:
    aircraft = _aircraft(squawk="0023", type_code="A189", operator="HM Coastguard Search and Rescue")
    departure = AirportInfo("Lee-on-Solent", "EGHF", None, "Lee-on-Solent", "GB", latitude_deg=50.815, longitude_deg=-1.21)
    arrival = AirportInfo("Newquay Airport", "EGHQ", "NQY", "Newquay", "GB", latitude_deg=50.4406, longitude_deg=-4.9954)
    route = AircraftRoute("TEST123", None, (departure, arrival))

    detail = format_stage20_aircraft_detail(aircraft, route=route)

    assert "Leonardo AW189" in detail
    assert "Role: Coastguard / Search & Rescue" in detail
    assert "Squawk: 0023 — Search & Rescue" in detail
    assert "Departure:" in detail
    assert "Departure time: unavailable from route source" in detail
    assert "Arrival:" in detail
    assert "ETA (estimated):" in detail
    assert detail.index("JOURNEY") < detail.index("LIVE TRACKING")
