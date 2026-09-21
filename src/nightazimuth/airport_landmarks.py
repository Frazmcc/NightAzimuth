from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class AirportLandmark:
    iata: str
    icao: str
    name: str
    latitude_deg: float
    longitude_deg: float
    distance_km: float
    bearing_deg: float


# Initial high-value Scottish reference airports. These are intentionally major
# airports only; NightAzimuth is not trying to render every aerodrome/airstrip.
_SCOTLAND_AIRPORTS: tuple[tuple[str, str, str, float, float], ...] = (
    ("GLA", "EGPF", "Glasgow Airport", 55.871899, -4.433060),
    ("PIK", "EGPK", "Glasgow Prestwick Airport", 55.501499, -4.577182),
    ("EDI", "EGPH", "Edinburgh Airport", 55.950145, -3.372288),
    ("ABZ", "EGPD", "Aberdeen International Airport", 57.201900, -2.197780),
)


def relevant_airport_landmarks(
    observer_latitude_deg: float,
    observer_longitude_deg: float,
    *,
    max_distance_km: float = 220.0,
    limit: int = 4,
) -> tuple[AirportLandmark, ...]:
    """Return only major nearby airports useful as horizon references."""
    landmarks: list[AirportLandmark] = []
    for iata, icao, name, latitude, longitude in _SCOTLAND_AIRPORTS:
        distance = _great_circle_km(
            observer_latitude_deg,
            observer_longitude_deg,
            latitude,
            longitude,
        )
        if distance > max_distance_km:
            continue
        landmarks.append(
            AirportLandmark(
                iata=iata,
                icao=icao,
                name=name,
                latitude_deg=latitude,
                longitude_deg=longitude,
                distance_km=distance,
                bearing_deg=_initial_bearing_deg(
                    observer_latitude_deg,
                    observer_longitude_deg,
                    latitude,
                    longitude,
                ),
            )
        )
    landmarks.sort(key=lambda item: item.distance_km)
    return tuple(landmarks[: max(0, int(limit))])


def airport_in_view(
    airport: AirportLandmark,
    facing_deg: float,
    horizontal_fov_deg: float,
) -> bool:
    half = max(1.0, horizontal_fov_deg / 2.0)
    delta = (airport.bearing_deg - facing_deg + 180.0) % 360.0 - 180.0
    return abs(delta) <= half


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return radius_km * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return math.degrees(math.atan2(y, x)) % 360.0
