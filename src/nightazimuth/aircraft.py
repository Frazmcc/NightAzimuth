from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Mapping, Sequence


FEET_TO_METRES = 0.3048
KNOTS_TO_METRES_PER_SECOND = 0.514444
MAX_POSITION_AGE_SECONDS = 30.0
_WGS84_A_METRES = 6_378_137.0
_WGS84_FLATTENING = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_FLATTENING * (2.0 - _WGS84_FLATTENING)


@dataclass(frozen=True, slots=True)
class AircraftPosition:
    hex_id: str
    callsign: str
    registration: str | None
    aircraft_type: str | None
    latitude: float
    longitude: float
    altitude_m: float
    altitude_source: str
    ground_speed_knots: float | None
    ground_track_deg: float | None
    true_heading_deg: float | None
    vertical_rate_fpm: float | None
    position_age_seconds: float


@dataclass(frozen=True, slots=True)
class AircraftSnapshot:
    aircraft: tuple[AircraftPosition, ...]
    fetched_at_utc: datetime
    source_name: str
    attribution: str
    source_url: str


@dataclass(frozen=True, slots=True)
class AircraftSightline:
    aircraft: AircraftPosition
    azimuth_deg: float
    elevation_deg: float
    horizontal_range_km: float
    slant_range_km: float


class AircraftDataError(RuntimeError):
    """Raised when an aircraft provider cannot return a usable snapshot."""


def parse_readsb_aircraft(
    payload: Mapping[str, object],
    *,
    max_position_age_seconds: float = MAX_POSITION_AGE_SECONDS,
) -> tuple[AircraftPosition, ...]:
    """Parse the common readsb/tar1090 aircraft schema conservatively."""

    raw_items = payload.get("ac", payload.get("aircraft", ()))
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
        raise AircraftDataError("Aircraft response does not contain an aircraft list.")

    result: list[AircraftPosition] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        latitude = _finite_float(raw.get("lat"))
        longitude = _finite_float(raw.get("lon"))
        if latitude is None or longitude is None or not (-90.0 <= latitude <= 90.0):
            continue
        if not -180.0 <= longitude <= 180.0:
            continue

        altitude_ft, altitude_source = _airborne_altitude(raw)
        if altitude_ft is None:
            continue

        position_age = _finite_float(raw.get("seen_pos"))
        if position_age is None:
            position_age = _finite_float(raw.get("seen"))
        if position_age is None or position_age < 0.0 or position_age > max_position_age_seconds:
            continue

        hex_id = str(raw.get("hex") or "").strip().lower()
        if not hex_id:
            continue
        callsign = str(raw.get("flight") or hex_id.upper()).strip() or hex_id.upper()
        result.append(
            AircraftPosition(
                hex_id=hex_id,
                callsign=callsign,
                registration=_optional_text(raw.get("r")),
                aircraft_type=_optional_text(raw.get("t")),
                latitude=latitude,
                longitude=longitude,
                altitude_m=altitude_ft * FEET_TO_METRES,
                altitude_source=altitude_source,
                ground_speed_knots=_nonnegative_float(raw.get("gs")),
                ground_track_deg=_normalised_angle(raw.get("track")),
                true_heading_deg=_normalised_angle(raw.get("true_heading")),
                vertical_rate_fpm=_vertical_rate(raw),
                position_age_seconds=position_age,
            )
        )
    return tuple(result)


def aircraft_sightline(
    aircraft: AircraftPosition,
    *,
    observer_latitude: float,
    observer_longitude: float,
    observer_altitude_m: float,
) -> AircraftSightline:
    """Calculate a WGS84 topocentric sightline from observer to aircraft."""

    observer = _geodetic_to_ecef(observer_latitude, observer_longitude, observer_altitude_m)
    target = _geodetic_to_ecef(aircraft.latitude, aircraft.longitude, aircraft.altitude_m)
    dx, dy, dz = (target[index] - observer[index] for index in range(3))
    lat = math.radians(observer_latitude)
    lon = math.radians(observer_longitude)
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = (
        -math.sin(lat) * math.cos(lon) * dx
        - math.sin(lat) * math.sin(lon) * dy
        + math.cos(lat) * dz
    )
    up = (
        math.cos(lat) * math.cos(lon) * dx
        + math.cos(lat) * math.sin(lon) * dy
        + math.sin(lat) * dz
    )
    horizontal = math.hypot(east, north)
    slant = math.hypot(horizontal, up)
    azimuth = math.degrees(math.atan2(east, north)) % 360.0
    elevation = math.degrees(math.atan2(up, horizontal))
    return AircraftSightline(
        aircraft=aircraft,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        horizontal_range_km=horizontal / 1000.0,
        slant_range_km=slant / 1000.0,
    )


def project_aircraft_position(
    aircraft: AircraftPosition,
    seconds_ahead: float,
) -> AircraftPosition:
    """Project a short movement cue from ground track/speed; not a flight-plan forecast."""

    seconds = max(0.0, float(seconds_ahead))
    speed = aircraft.ground_speed_knots
    track = aircraft.ground_track_deg
    if speed is None or track is None or seconds == 0.0:
        return aircraft

    distance = speed * KNOTS_TO_METRES_PER_SECOND * seconds
    angular_distance = distance / _WGS84_A_METRES
    bearing = math.radians(track)
    lat1 = math.radians(aircraft.latitude)
    lon1 = math.radians(aircraft.longitude)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    climb_m = (aircraft.vertical_rate_fpm or 0.0) * FEET_TO_METRES * seconds / 60.0
    return AircraftPosition(
        hex_id=aircraft.hex_id,
        callsign=aircraft.callsign,
        registration=aircraft.registration,
        aircraft_type=aircraft.aircraft_type,
        latitude=math.degrees(lat2),
        longitude=(math.degrees(lon2) + 180.0) % 360.0 - 180.0,
        altitude_m=aircraft.altitude_m + climb_m,
        altitude_source=aircraft.altitude_source,
        ground_speed_knots=aircraft.ground_speed_knots,
        ground_track_deg=aircraft.ground_track_deg,
        true_heading_deg=aircraft.true_heading_deg,
        vertical_rate_fpm=aircraft.vertical_rate_fpm,
        position_age_seconds=aircraft.position_age_seconds + seconds,
    )


def _geodetic_to_ecef(latitude: float, longitude: float, altitude_m: float) -> tuple[float, float, float]:
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    sin_lat = math.sin(lat)
    radius = _WGS84_A_METRES / math.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
    return (
        (radius + altitude_m) * math.cos(lat) * math.cos(lon),
        (radius + altitude_m) * math.cos(lat) * math.sin(lon),
        (radius * (1.0 - _WGS84_E2) + altitude_m) * sin_lat,
    )


def _airborne_altitude(raw: Mapping[str, object]) -> tuple[float | None, str]:
    geometric = _finite_float(raw.get("alt_geom"))
    if geometric is not None:
        return geometric, "geometric"
    barometric = _finite_float(raw.get("alt_baro"))
    if barometric is not None:
        return barometric, "barometric"
    return None, ""


def _vertical_rate(raw: Mapping[str, object]) -> float | None:
    geometric = _finite_float(raw.get("geom_rate"))
    if geometric is not None:
        return geometric
    return _finite_float(raw.get("baro_rate"))


def _finite_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _nonnegative_float(value: object) -> float | None:
    result = _finite_float(value)
    return result if result is not None and result >= 0.0 else None


def _normalised_angle(value: object) -> float | None:
    result = _finite_float(value)
    return None if result is None else result % 360.0


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
