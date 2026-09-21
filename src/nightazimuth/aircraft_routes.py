from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True, slots=True)
class AirportInfo:
    name: str
    icao: str | None
    iata: str | None
    location: str | None
    country_iso2: str | None
    country_name: str | None = None
    latitude_deg: float | None = None
    longitude_deg: float | None = None

    @property
    def display_code(self) -> str:
        if self.iata and self.icao:
            return f"{self.iata} / {self.icao}"
        return self.iata or self.icao or "Unknown"

    @property
    def display_country(self) -> str:
        return self.country_name or self.country_iso2 or "Unknown"


@dataclass(frozen=True, slots=True)
class AircraftRoute:
    callsign: str
    airline_code: str | None
    airports: tuple[AirportInfo, ...]
    source_label: str = "adsb.lol standing data"

    @property
    def departure(self) -> AirportInfo | None:
        return self.airports[0] if self.airports else None

    @property
    def arrival(self) -> AirportInfo | None:
        return self.airports[-1] if len(self.airports) >= 2 else None

    @property
    def intermediate_airports(self) -> tuple[AirportInfo, ...]:
        return self.airports[1:-1] if len(self.airports) > 2 else ()


@dataclass(frozen=True, slots=True)
class _CachedRoute:
    value: AircraftRoute | None
    expires_at: datetime


class AdsbLolRouteProvider:
    """Lazy cached route lookup using adsb.lol's CC0 standing-data service."""

    BASE_URL = "https://vrs-standing-data.adsb.lol/routes"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 4.0,
        cache_hours: float = 6.0,
        negative_cache_minutes: float = 30.0,
        user_agent: str = "NightAzimuth/1.0 (+https://github.com/Frazmcc/NightAzimuth)",
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._cache_age = timedelta(hours=max(0.1, cache_hours))
        self._negative_cache_age = timedelta(minutes=max(1.0, negative_cache_minutes))
        self._user_agent = user_agent
        self._cache: dict[str, _CachedRoute] = {}
        self._lock = Lock()

    def lookup(self, callsign: str | None) -> AircraftRoute | None:
        key = _normalise_callsign(callsign)
        if key is None:
            return None

        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.expires_at > now:
                return cached.value

        route = self._fetch(key)
        ttl = self._cache_age if route is not None else self._negative_cache_age
        with self._lock:
            self._cache[key] = _CachedRoute(route, now + ttl)
        return route

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _fetch(self, callsign: str) -> AircraftRoute | None:
        prefix = quote(callsign[:2], safe="")
        encoded = quote(callsign, safe="")
        url = f"{self.BASE_URL}/{prefix}/{encoded}.json"
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        try:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        finally:
            if owns_client:
                client.close()

        return _parse_route(payload, expected_callsign=callsign)


def _normalise_callsign(value: str | None) -> str | None:
    if value is None:
        return None
    callsign = value.strip().upper().replace(" ", "")
    if len(callsign) < 2 or len(callsign) > 12:
        return None
    if not callsign.isalnum():
        return None
    return callsign


def _parse_route(payload: Any, *, expected_callsign: str) -> AircraftRoute | None:
    if not isinstance(payload, dict):
        return None
    airports_raw = payload.get("_airports")
    if not isinstance(airports_raw, list):
        return None

    airports = tuple(
        airport
        for row in airports_raw
        if isinstance(row, dict)
        if (airport := _parse_airport(row)) is not None
    )
    if len(airports) < 2:
        return None

    callsign = str(payload.get("callsign") or expected_callsign).strip().upper()
    airline_code = str(payload.get("airline_code") or "").strip().upper() or None
    return AircraftRoute(callsign=callsign, airline_code=airline_code, airports=airports)


def _parse_airport(row: dict[str, Any]) -> AirportInfo | None:
    name = str(row.get("name") or "").strip()
    if not name:
        return None
    icao = str(row.get("icao") or "").strip().upper() or None
    iata = str(row.get("iata") or "").strip().upper() or None
    location = str(row.get("location") or "").strip() or None
    country_iso2 = str(row.get("countryiso2") or "").strip().upper() or None
    country_name = str(
        row.get("country_name") or row.get("country") or ""
    ).strip() or None
    latitude_deg = _optional_float(row.get("lat"))
    longitude_deg = _optional_float(row.get("lon"))
    return AirportInfo(
        name=name,
        icao=icao,
        iata=iata,
        location=location,
        country_iso2=country_iso2,
        country_name=country_name,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
    )


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
