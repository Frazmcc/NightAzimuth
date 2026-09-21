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


@dataclass(frozen=True, slots=True)
class AirportLandmark:
    iata: str
    icao: str
    name: str
    latitude_deg: float
    longitude_deg: float
    distance_km: float
    bearing_deg: float


class AirportLandmarkProvider:
    """Location-neutral airport reference provider backed by global public data."""

    DATA_URL = "https://vrs-standing-data.adsb.lol/airports.csv.gz"

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
                )
            )
        landmarks.sort(key=lambda item: item.distance_km)
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
            headers={"User-Agent": "NightAzimuth/1.0", "Accept": "application/gzip,text/csv"},
            follow_redirects=True,
        )
        try:
            response = client.get(self.DATA_URL)
            response.raise_for_status()
            raw = gzip.decompress(response.content)
            text = raw.decode("utf-8-sig")
        except (httpx.HTTPError, OSError, UnicodeDecodeError):
            return ()
        finally:
            if owns_client:
                client.close()

        records: list[AirportRecord] = []
        for row in csv.DictReader(io.StringIO(text)):
            iata = (row.get("IATA") or "").strip().upper()
            icao = (row.get("ICAO") or "").strip().upper()
            name = (row.get("Name") or "").strip()
            if len(iata) != 3 or len(icao) != 4 or not name:
                continue
            try:
                latitude = float(row.get("Latitude") or "")
                longitude = float(row.get("Longitude") or "")
            except ValueError:
                continue
            if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
                continue
            records.append(AirportRecord(iata, icao, name, latitude, longitude))
        return tuple(records)


_DEFAULT_PROVIDER = AirportLandmarkProvider()


def relevant_airport_landmarks(
    observer_latitude_deg: float,
    observer_longitude_deg: float,
    *,
    max_distance_km: float = 220.0,
    limit: int = 4,
) -> tuple[AirportLandmark, ...]:
    """Resolve nearby airport references solely from the selected observer location."""
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
