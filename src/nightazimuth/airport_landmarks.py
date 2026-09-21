from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
import io
import math
from threading import Lock

import httpx


@dataclass(frozen=True, slots=True)
class AirportRecord:
    iata: str
    icao: str
    name: str
    latitude_deg: float
    longitude_deg: float
    airport_type: str = ""
    scheduled_service: bool = False


@dataclass(frozen=True, slots=True)
class AirportLandmark:
    iata: str
    icao: str
    name: str
    latitude_deg: float
    longitude_deg: float
    distance_km: float
    bearing_deg: float
    airport_type: str = ""
    scheduled_service: bool = False


class AirportLandmarkProvider:
    """Location-neutral major-airport references from a global public dataset."""

    # OurAirports publishes a global public-domain CSV and exposes airport class
    # plus scheduled-service state, which lets NightAzimuth avoid flooding the
    # horizon with small local strips without hard-coding any region.
    DATA_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
        cache_hours: float = 24.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._cache_age = timedelta(hours=max(1.0, cache_hours))
        self._records: tuple[AirportRecord, ...] = ()
        self._loaded_at: datetime | None = None
        self._lock = Lock()

    def nearby(
        self,
        observer_latitude_deg: float,
        observer_longitude_deg: float,
        *,
        max_distance_km: float = 220.0,
        limit: int = 4,
    ) -> tuple[AirportLandmark, ...]:
        records = self._load_records()
        landmarks: list[AirportLandmark] = []
        for airport in records:
            distance = _great_circle_km(
                observer_latitude_deg,
                observer_longitude_deg,
                airport.latitude_deg,
                airport.longitude_deg,
            )
            if distance > max_distance_km:
                continue
            landmarks.append(
                AirportLandmark(
                    iata=airport.iata,
                    icao=airport.icao,
                    name=airport.name,
                    latitude_deg=airport.latitude_deg,
                    longitude_deg=airport.longitude_deg,
                    distance_km=distance,
                    bearing_deg=_initial_bearing_deg(
                        observer_latitude_deg,
                        observer_longitude_deg,
                        airport.latitude_deg,
                        airport.longitude_deg,
                    ),
                    airport_type=airport.airport_type,
                    scheduled_service=airport.scheduled_service,
                )
            )

        # Prefer genuinely significant airports over simply taking the nearest
        # IATA-coded strips. Where no large airport is nearby, scheduled regional
        # airports naturally become the next-best references.
        landmarks.sort(key=_landmark_priority)
        return tuple(landmarks[: max(0, int(limit))])

    def _load_records(self) -> tuple[AirportRecord, ...]:
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._records and self._loaded_at is not None and now - self._loaded_at < self._cache_age:
                return self._records

        records = self._fetch_records()
        with self._lock:
            if records:
                self._records = records
                self._loaded_at = now
            return self._records

    def _fetch_records(self) -> tuple[AirportRecord, ...]:
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "NightAzimuth/1.1", "Accept": "text/csv,application/gzip"},
            follow_redirects=True,
        )
        try:
            response = client.get(self.DATA_URL)
            response.raise_for_status()
            payload = response.content
            if payload.startswith(b"\x1f\x8b"):
                payload = gzip.decompress(payload)
            text = payload.decode("utf-8-sig")
        except (httpx.HTTPError, OSError, UnicodeDecodeError):
            return ()
        finally:
            if owns_client:
                client.close()

        records: list[AirportRecord] = []
        for row in csv.DictReader(io.StringIO(text)):
            iata = _first(row, "iata_code", "IATA", "iata").upper()
            icao = _first(row, "ident", "ICAO", "icao", "gps_code").upper()
            name = _first(row, "name", "Name")
            airport_type = _first(row, "type", "airport_type").lower()
            scheduled = _first(row, "scheduled_service").lower() in {"yes", "true", "1"}
            if len(iata) != 3 or len(icao) != 4 or not name:
                continue
            if airport_type in {"closed", "heliport", "seaplane_base", "balloonport"}:
                continue
            try:
                latitude = float(_first(row, "latitude_deg", "latitude", "Latitude"))
                longitude = float(_first(row, "longitude_deg", "longitude", "Longitude"))
            except ValueError:
                continue
            if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
                continue
            records.append(
                AirportRecord(
                    iata=iata,
                    icao=icao,
                    name=name,
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    airport_type=airport_type,
                    scheduled_service=scheduled,
                )
            )
        return tuple(records)


_DEFAULT_PROVIDER = AirportLandmarkProvider()


def relevant_airport_landmarks(
    observer_latitude_deg: float,
    observer_longitude_deg: float,
    *,
    max_distance_km: float = 220.0,
    limit: int = 4,
) -> tuple[AirportLandmark, ...]:
    """Resolve a sparse set of significant airports from the selected location."""
    return _DEFAULT_PROVIDER.nearby(
        observer_latitude_deg,
        observer_longitude_deg,
        max_distance_km=max_distance_km,
        limit=limit,
    )


def airport_in_view(
    airport: AirportLandmark,
    facing_deg: float,
    horizontal_fov_deg: float,
) -> bool:
    half = max(1.0, horizontal_fov_deg / 2.0)
    delta = (airport.bearing_deg - facing_deg + 180.0) % 360.0 - 180.0
    return abs(delta) <= half


def _landmark_priority(airport: AirportLandmark) -> tuple[int, float, str]:
    if airport.airport_type == "large_airport":
        class_priority = 0
    elif airport.airport_type == "medium_airport" and airport.scheduled_service:
        class_priority = 1
    elif airport.airport_type == "medium_airport":
        class_priority = 2
    elif airport.scheduled_service:
        class_priority = 3
    else:
        class_priority = 4
    return class_priority, airport.distance_km, airport.icao


def _first(row: dict[str, str | None], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return radius_km * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def _initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return math.degrees(math.atan2(y, x)) % 360.0
