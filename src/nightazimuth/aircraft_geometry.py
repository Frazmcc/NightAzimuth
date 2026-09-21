from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin, sqrt

from .aircraft import AircraftObservation, AircraftObserver

# WGS84 ellipsoid.
_WGS84_A_M = 6378137.0
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)


@dataclass(frozen=True, slots=True)
class AircraftSkyPosition:
    azimuth_deg: float
    elevation_deg: float
    slant_range_m: float
    altitude_m: float
    altitude_source: str


def aircraft_sky_position(
    observer: AircraftObserver,
    aircraft: AircraftObservation,
) -> AircraftSkyPosition | None:
    """Convert an aircraft geodetic fix into observer-relative sky coordinates."""
    if aircraft.geometric_altitude_m is not None:
        altitude_m = aircraft.geometric_altitude_m
        altitude_source = "geometric"
    elif aircraft.barometric_altitude_m is not None:
        altitude_m = aircraft.barometric_altitude_m
        altitude_source = "barometric"
    else:
        return None

    observer_ecef = _geodetic_to_ecef(
        observer.latitude_deg,
        observer.longitude_deg,
        observer.altitude_m,
    )
    aircraft_ecef = _geodetic_to_ecef(
        aircraft.latitude_deg,
        aircraft.longitude_deg,
        altitude_m,
    )
    dx = aircraft_ecef[0] - observer_ecef[0]
    dy = aircraft_ecef[1] - observer_ecef[1]
    dz = aircraft_ecef[2] - observer_ecef[2]

    lat = radians(observer.latitude_deg)
    lon = radians(observer.longitude_deg)
    sin_lat, cos_lat = sin(lat), cos(lat)
    sin_lon, cos_lon = sin(lon), cos(lon)

    east = -sin_lon * dx + cos_lon * dy
    north = (
        -sin_lat * cos_lon * dx
        - sin_lat * sin_lon * dy
        + cos_lat * dz
    )
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    horizontal = hypot(east, north)
    slant = sqrt(east * east + north * north + up * up)
    if slant <= 0.0:
        return None

    azimuth = degrees(atan2(east, north)) % 360.0
    elevation = degrees(atan2(up, horizontal))
    return AircraftSkyPosition(
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        slant_range_m=slant,
        altitude_m=altitude_m,
        altitude_source=altitude_source,
    )


def _geodetic_to_ecef(
    latitude_deg: float,
    longitude_deg: float,
    altitude_m: float,
) -> tuple[float, float, float]:
    lat = radians(latitude_deg)
    lon = radians(longitude_deg)
    sin_lat, cos_lat = sin(lat), cos(lat)
    sin_lon, cos_lon = sin(lon), cos(lon)
    prime_vertical = _WGS84_A_M / sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)

    x = (prime_vertical + altitude_m) * cos_lat * cos_lon
    y = (prime_vertical + altitude_m) * cos_lat * sin_lon
    z = (prime_vertical * (1.0 - _WGS84_E2) + altitude_m) * sin_lat
    return x, y, z
