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
    """Present selected-aircraft information in observer-first order."""
    identity = aircraft_display_identity(aircraft)
    altitude_ft = aircraft.altitude_m / 0.3048
    speed_knots = None if aircraft.ground_speed_mps is None else aircraft.ground_speed_mps / 0.514444
    vertical_fpm = None if aircraft.vertical_rate_mps is None else aircraft.vertical_rate_mps / 0.00508

    lines: list[str] = [aircraft.callsign or aircraft.registration or "Aircraft"]

    model_line = identity.make_model
    if identity.capacity:
        model_line += f" ({identity.capacity})"
    lines.append(model_line)
    if identity.role:
        lines.append(f"Role: {identity.role}")
    if aircraft.operator:
        lines.append(f"Operator: {aircraft.operator}")
    if aircraft.registration:
        lines.append(f"Registration: {aircraft.registration}")

    squawk = squawk_display(aircraft)
    if squawk:
        lines.append(f"Squawk: {squawk}")

    lines.extend(("", "JOURNEY"))
    lines.extend(_format_journey(aircraft, route))

    lines.extend(("", "LIVE TRACKING"))
    lines.append(f"Altitude: {altitude_ft:,.0f} ft")
    if speed_knots is not None:
        lines.append(f"Ground speed: {speed_knots:.0f} kt")
    if aircraft.track_deg is not None:
        lines.append(f"Track: {aircraft.track_deg:.0f}°")
    if vertical_fpm is not None:
        lines.append(f"Vertical rate: {vertical_fpm:+.0f} ft/min")
    lines.extend(
        (
            f"Azimuth: {aircraft.azimuth_deg:.1f}°",
            f"Elevation: {aircraft.elevation_deg:.1f}°",
            f"Range: {aircraft.range_km:.1f} km",
            f"ICAO hex: {aircraft.icao24.upper()}",
            f"Position: {aircraft.position_state.value} · age {aircraft.position_age_seconds:.1f}s",
            f"Source: {aircraft.source_label}",
        )
    )
    return "\n".join(lines)


def _format_journey(aircraft: SkyAircraft, route: AircraftRoute | None) -> list[str]:
    if route is None or route.departure is None or route.arrival is None:
        return [
            "Departure: Unknown",
            "Departure time: Unknown",
            "Arrival: Unknown",
            "ETA: Unknown",
        ]

    departure = route.departure
    arrival = route.arrival
    lines = [
        f"Departure: {_airport_summary(departure)}",
        "Departure time: unavailable from route source",
    ]
    if route.intermediate_airports:
        via = " → ".join(airport.display_code for airport in route.intermediate_airports)
        lines.append(f"Via: {via}")
    lines.append(f"Arrival: {_airport_summary(arrival)}")

    eta = estimate_arrival_time(aircraft, arrival)
    if eta is None:
        lines.append("ETA: Unknown")
    else:
        eta_time, minutes = eta
        lines.append(f"ETA (estimated): {eta_time:%H:%M} UTC · ~{minutes:d} min")
    return lines


def _airport_summary(airport: AirportInfo) -> str:
    location = f", {airport.location}" if airport.location else ""
    country = f", {airport.display_country}" if airport.display_country != "Unknown" else ""
    return f"{airport.display_code} — {airport.name}{location}{country}"


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
    # A small bounded allowance avoids displaying an over-optimistic gate-like
    # arrival while still keeping this a lightweight estimate, not a flight model.
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
