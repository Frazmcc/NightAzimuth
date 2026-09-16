from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Protocol
from urllib.parse import urlparse

import httpx

from .aircraft import AircraftDataError, AircraftPosition, AircraftSnapshot, parse_readsb_aircraft


ADSB_LOL_API_ROOT = "https://api.adsb.lol"
ADSB_LOL_ATTRIBUTION = "Aircraft data: ADSB.lol — ODbL 1.0"
DEFAULT_LOCAL_READSB_URL = "http://127.0.0.1:8080/data/aircraft.json"
USER_AGENT = "NightAzimuth/1.0 (free aircraft sightline overlay)"
_EARTH_RADIUS_NM = 3440.065


class AircraftProvider(Protocol):
    def load(self, latitude: float, longitude: float, radius_nm: float) -> AircraftSnapshot: ...


class AdsbLolAircraftProvider:
    """No-key live aircraft source documented as open under ODbL 1.0."""

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 10.0) -> None:
        self._client = client
        self.timeout_seconds = timeout_seconds

    def load(self, latitude: float, longitude: float, radius_nm: float) -> AircraftSnapshot:
        latitude, longitude, radius = _validated_query(latitude, longitude, radius_nm)
        url = f"{ADSB_LOL_API_ROOT}/v2/point/{latitude:.6f}/{longitude:.6f}/{radius:.1f}"
        payload = self._get_json(url)
        aircraft = _within_radius(
            parse_readsb_aircraft(payload),
            latitude=latitude,
            longitude=longitude,
            radius_nm=radius,
        )
        return AircraftSnapshot(
            aircraft=aircraft,
            fetched_at_utc=datetime.now(timezone.utc),
            source_name="ADSB.lol",
            attribution=ADSB_LOL_ATTRIBUTION,
            source_url=ADSB_LOL_API_ROOT,
        )

    def _get_json(self, url: str) -> dict[str, object]:
        try:
            if self._client is not None:
                response = self._client.get(url, headers={"User-Agent": USER_AGENT})
            else:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                    response = client.get(url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AircraftDataError("ADSB.lol aircraft refresh failed.") from exc
        if not isinstance(payload, dict):
            raise AircraftDataError("ADSB.lol returned an unexpected response.")
        return payload


class LocalReadsbAircraftProvider:
    """Read aircraft.json from a user-configured readsb/dump1090 receiver."""

    def __init__(
        self,
        url: str = DEFAULT_LOCAL_READSB_URL,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 4.0,
    ) -> None:
        self.url = validate_local_receiver_url(url)
        self._client = client
        self.timeout_seconds = timeout_seconds

    def load(self, latitude: float, longitude: float, radius_nm: float) -> AircraftSnapshot:
        latitude, longitude, radius = _validated_query(latitude, longitude, radius_nm)
        try:
            if self._client is not None:
                response = self._client.get(self.url, headers={"User-Agent": USER_AGENT})
            else:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                    response = client.get(self.url, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AircraftDataError("Local aircraft receiver refresh failed.") from exc
        if not isinstance(payload, dict):
            raise AircraftDataError("Local aircraft receiver returned an unexpected response.")
        aircraft = _within_radius(
            parse_readsb_aircraft(payload),
            latitude=latitude,
            longitude=longitude,
            radius_nm=radius,
        )
        return AircraftSnapshot(
            aircraft=aircraft,
            fetched_at_utc=datetime.now(timezone.utc),
            source_name="Local readsb/dump1090",
            attribution="Aircraft data: local receiver",
            source_url=self.url,
        )


def validate_local_receiver_url(value: object) -> str:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Local receiver URL must be a complete http:// or https:// URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Local receiver URL must not contain credentials.")
    return candidate


def _validated_query(latitude: float, longitude: float, radius_nm: float) -> tuple[float, float, float]:
    lat = float(latitude)
    lon = float(longitude)
    radius = float(radius_nm)
    if not -90.0 <= lat <= 90.0:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("Longitude must be between -180 and 180.")
    if not 1.0 <= radius <= 250.0:
        raise ValueError("Aircraft search radius must be between 1 and 250 nautical miles.")
    return lat, lon, radius


def _within_radius(
    aircraft: tuple[AircraftPosition, ...],
    *,
    latitude: float,
    longitude: float,
    radius_nm: float,
) -> tuple[AircraftPosition, ...]:
    return tuple(
        item
        for item in aircraft
        if _great_circle_distance_nm(latitude, longitude, item.latitude, item.longitude) <= radius_nm
    )


def _great_circle_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    haversine = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    central_angle = 2.0 * math.atan2(math.sqrt(haversine), math.sqrt(max(0.0, 1.0 - haversine)))
    return _EARTH_RADIUS_NM * central_angle
