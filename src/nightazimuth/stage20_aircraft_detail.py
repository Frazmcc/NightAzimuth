from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

from .aircraft_display import aircraft_display_identity, squawk_display
from .aircraft_live import SkyAircraft
from .aircraft_routes import AircraftRoute, AirportInfo

EARTH_RADIUS_KM = 6371.0


def format_stage20_aircraft_detail(
    aircraft: SkyAircraft,
    *,
    route: AircraftRoute | None = None,
) -> str:
    """Present selected-aircraft information compactly in observer-first order."""
    identity = aircraft_display_identity(aircraft)
    altitude_ft = aircraft.altitude_m / 0.3048
    speed_knots = None if aircraft.ground_speed_mps is None else aircraft.ground_speed_mps / 0.514444
    vertical_fpm = None if aircraft.vertical_rate_mps is None else aircraft.vertical_rate_mps / 0.00508

    headline = aircraft.callsign or aircraft.registration or aircraft.icao24.upper()
    model_line = identity.make_model
    if identity.capacity:
        model_line += f" ({identity.capacity})"

    lines: list[str] = [headline, model_line]

    identity_bits: list[str] = []
    if identity.role:
        identity_bits.append(f"Role: {identity.role}")
    if aircraft.operator:
        identity_bits.append(f"Operator: {aircraft.operator}")
    if identity_bits:
        lines.append(" • ".join(identity_bits))

    squawk = squawk_display(aircraft)
    if squawk:
        lines.append(f"Squawk: {squawk}")

    lines.extend(("", "JOURNEY"))
    lines.extend(_format_journey(aircraft, route))

    tracking_bits = [f"{altitude_ft:,.0f} ft"]
    if speed_knots is not None:
        tracking_bits.append(f"{speed_knots:.0f} kt")
    if aircraft.track_deg is not None:
        tracking_bits.append(f"Track {aircraft.track_deg:.0f}°")
    if vertical_fpm is not None:
        tracking_bits.append(f"Vertical {vertical_fpm:+.0f} ft/min")
    tracking_bits.append(f"Range {aircraft.range_km:.1f} km")

    lines.extend(("", "LIVE TRACKING", " • ".join(tracking_bits)))
    lines.append(
        f"Az {aircraft.azimuth_deg:.1f}° • El {aircraft.elevation_deg:.1f}° • "
        f"{aircraft.position_state.value} • age {aircraft.position_age_seconds:.1f}s"
    )

    technical_bits = [f"ICAO {aircraft.icao24.upper()}"]
    if aircraft.registration:
        technical_bits.append(f"Reg {aircraft.registration}")
    technical_bits.append(f"Source {aircraft.source_label}")
    lines.append(" • ".join(technical_bits))
    return "\n".join(lines)


def _format_journey(aircraft: SkyAircraft, route: AircraftRoute | None) -> list[str]:
    if route is None or route.departure is None or route.arrival is None:
        return [
            "Departure: Unknown • Departure time: Unknown",
            "Arrival: Unknown • ETA: Unknown",
        ]

    departure = route.departure
    arrival = route.arrival
    route_line = f"{_airport_summary(departure)}"
    if route.intermediate_airports:
        via = " → ".join(airport.display_code for airport in route.intermediate_airports)
        route_line += f" → {via}"
    route_line += f" → {_airport_summary(arrival)}"

    lines = [route_line, "Departure time: unavailable from route source"]
    eta = estimate_arrival_time(aircraft, arrival)
    if eta is None:
        lines.append("ETA: Unknown")
    else:
        eta_time, minutes = eta
        lines.append(f"ETA: {eta_time:%H:%M} UTC (estimated, ~{minutes:d} min)")
    return lines


def _airport_summary(airport: AirportInfo) -> str:
    code = airport.display_code
    name = airport.name
    return f"{code} {name}" if name and name != code else code


def estimate_arrival_time(
    aircraft: SkyAircraft,
    arrival: AirportInfo,
    *,
    now: datetime | None = None,
) -> tuple[datetime, int] | None:
    """Estimate arrival from current great-circle distance and groundspeed.

    This is deliberately labelled as an estimate: it does not model routing,
    vectors, holds, descent profile or taxi time.
    """
    if (
        aircraft.latitude_deg is None
        or aircraft.longitude_deg is None
        or arrival.latitude_deg is None
        or arrival.longitude_deg is None
        or aircraft.ground_speed_mps is None
        or aircraft.ground_speed_mps < 30.0
    ):
        return None

    distance_km = _great_circle_km(
        aircraft.latitude_deg,
        aircraft.longitude_deg,
        arrival.latitude_deg,
        arrival.longitude_deg,
    )
    speed_kmh = aircraft.ground_speed_mps * 3.6
    hours = distance_km / max(speed_kmh, 1.0)
    hours += min(0.20, max(0.05, distance_km / 5000.0))
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        moment = moment.replace(tzinfo=timezone.utc)
    eta = moment.astimezone(timezone.utc) + timedelta(hours=hours)
    return eta, max(1, int(round(hours * 60.0)))


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
