from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import math
from threading import Lock

import httpx

from .airport_landmarks import AirportLandmark


@dataclass(frozen=True, slots=True)
class _Airport:
    iata: str
    icao: str
    name: str
    latitude_deg: float
    longitude_deg: float
    airport_type: str = ""
    scheduled_service: bool = False


class ResilientAirportLandmarkProvider:
    """Global, location-neutral airport landmarks with provider fallback.

    OurAirports is preferred because it exposes airport size and scheduled
    service. ADSB.lol standing data is a compact fallback so a slow/unavailable
    primary source never removes the horizon reference layer completely.
    """

    PRIMARY_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    FALLBACK_URL = "https://vrs-standing-data.adsb.lol/airports.csv"

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 20.0) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._records: tuple[_Airport, ...] = ()
        self._lock = Lock()

    def nearby(
        self,
        observer_latitude_deg: float,
        observer_longitude_deg: float,
        *,
        max_distance_km: float = 250.0,
        limit: int = 12,
    ) -> tuple[AirportLandmark, ...]:
        records = self._load_records()
        landmarks: list[tuple[AirportLandmark, bool]] = []
        for airport in records:
            distance = _great_circle_km(
                observer_latitude_deg,
                observer_longitude_deg,
                airport.latitude_deg,
                airport.longitude_deg,
            )
            if distance > max_distance_km:
                continue
            landmark = AirportLandmark(
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
            )
            landmarks.append((landmark, airport.scheduled_service))

        landmarks.sort(key=lambda pair: _priority(pair[0], pair[1]))
        return tuple(item for item, _scheduled in landmarks[: max(0, int(limit))])

    def _load_records(self) -> tuple[_Airport, ...]:
        with self._lock:
            if self._records:
                return self._records

        records = self._fetch_ourairports()
        if not records:
            records = self._fetch_adsb_lol()

        with self._lock:
            if records:
                self._records = records
            return self._records

    def _get_text(self, url: str) -> str | None:
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "NightAzimuth/1.1", "Accept": "text/csv"},
        )
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content.decode("utf-8-sig")
        except (httpx.HTTPError, UnicodeDecodeError):
            return None
        finally:
            if owns_client:
                client.close()

    def _fetch_ourairports(self) -> tuple[_Airport, ...]:
        text = self._get_text(self.PRIMARY_URL)
        if not text:
            return ()
        records: list[_Airport] = []
        for row in csv.DictReader(io.StringIO(text)):
            iata = (row.get("iata_code") or "").strip().upper()
            icao = (row.get("ident") or row.get("gps_code") or "").strip().upper()
            name = (row.get("name") or "").strip()
            airport_type = (row.get("type") or "").strip().lower()
            scheduled = (row.get("scheduled_service") or "").strip().lower() == "yes"
            if len(iata) != 3 or len(icao) != 4 or not name:
                continue
            if airport_type not in {"large_airport", "medium_airport"}:
                continue
            if airport_type == "medium_airport" and not scheduled:
                continue
            try:
                latitude = float(row.get("latitude_deg") or "")
                longitude = float(row.get("longitude_deg") or "")
            except ValueError:
                continue
            records.append(
                _Airport(
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

    def _fetch_adsb_lol(self) -> tuple[_Airport, ...]:
        text = self._get_text(self.FALLBACK_URL)
        if not text:
            return ()
        records: list[_Airport] = []
        for row in csv.DictReader(io.StringIO(text)):
            iata = (row.get("IATA") or "").strip().upper()
            icao = (row.get("ICAO") or row.get("Code") or "").strip().upper()
            name = (row.get("Name") or "").strip()
            if len(iata) != 3 or len(icao) != 4 or not name:
                continue
            try:
                latitude = float(row.get("Latitude") or "")
                longitude = float(row.get("Longitude") or "")
            except ValueError:
                continue
            records.append(
                _Airport(
                    iata=iata,
                    icao=icao,
                    name=name,
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    airport_type="fallback",
                    scheduled_service=True,
                )
            )
        return tuple(records)


def _priority(airport: AirportLandmark, scheduled: bool) -> tuple[int, int, float, str]:
    if airport.airport_type == "large_airport":
        size = 0
    elif airport.airport_type == "medium_airport":
        size = 1
    else:
        size = 2
    return size, -int(scheduled), airport.distance_km, airport.icao


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
