from __future__ import annotations

import csv
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import ObserverConfig

_HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
_ROADSTER_TARGET_ID = "-143205"
_AU_KM = 149_597_870.7
_MISSING_VALUES = {"", "n.a.", "na", "null", "none", "--"}


@dataclass(frozen=True, slots=True)
class RoadsterEphemeris:
    id: str
    name: str
    object_type: str
    international_designator: str
    jpl_target_id: str
    launch_date: str
    launch_vehicle: str
    payload: str
    body_colour: str
    tracking_mode: str
    data_source: str
    ephemeris_at: str
    azimuth_deg: float
    elevation_deg: float
    right_ascension_deg: float | None
    declination_deg: float | None
    apparent_magnitude: float | None
    distance_earth_au: float | None
    distance_earth_km: float | None
    distance_sun_au: float | None
    earth_range_rate_km_s: float | None
    heliocentric_speed_km_s: float | None
    observer_relative_speed_km_s: float | None
    light_time_minutes: float | None
    solar_elongation_deg: float | None
    phase_angle_deg: float | None
    heliocentric_ecliptic_longitude_deg: float | None
    heliocentric_ecliptic_latitude_deg: float | None
    constellation: str | None


@dataclass(frozen=True, slots=True)
class _CachedRoadster:
    value: RoadsterEphemeris
    expires_at: datetime


class RoadsterEphemerisProvider:
    """Fail-soft, short-lived JPL Horizons ephemeris for the Tesla Roadster."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
        cache_minutes: float = 10.0,
        max_cache_entries: int = 64,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._cache_age = timedelta(minutes=max(1.0, cache_minutes))
        self._max_cache_entries = max(4, max_cache_entries)
        self._cache: dict[tuple[float, float, float], _CachedRoadster] = {}
        self._lock = threading.Lock()

    def lookup(
        self,
        observer: ObserverConfig,
        *,
        when: datetime | None = None,
    ) -> RoadsterEphemeris | None:
        instant = _as_utc(when or datetime.now(UTC))
        key = (
            round(float(observer.latitude), 3),
            round(float(observer.longitude), 3),
            round(float(observer.altitude_m), -1),
        )
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.expires_at > instant:
                return cached.value

        try:
            value = self._fetch(observer, instant)
        except (httpx.HTTPError, ValueError, KeyError, csv.Error):
            # A stale result is preferable to removing the Roadster marker during a
            # transient Horizons outage. The API layer still labels the ephemeris time.
            return cached.value if cached is not None else None

        with self._lock:
            self._cache[key] = _CachedRoadster(value=value, expires_at=instant + self._cache_age)
            while len(self._cache) > self._max_cache_entries:
                oldest_key = next(iter(self._cache))
                if oldest_key == key and len(self._cache) > 1:
                    oldest_key = next(item for item in self._cache if item != key)
                self._cache.pop(oldest_key, None)
        return value

    def _fetch(self, observer: ObserverConfig, when: datetime) -> RoadsterEphemeris:
        altitude_km = float(observer.altitude_m) / 1000.0
        parameters = {
            "format": "json",
            "COMMAND": f"'{_ROADSTER_TARGET_ID}'",
            "OBJ_DATA": "'NO'",
            "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'",
            "CENTER": "'coord@399'",
            "COORD_TYPE": "'GEODETIC'",
            "SITE_COORD": (
                f"'{float(observer.longitude):.6f},"
                f"{float(observer.latitude):.6f},{altitude_km:.3f}'"
            ),
            "TLIST": f"'{when.strftime('%Y-%b-%d %H:%M:%S')}'",
            "TLIST_TYPE": "'CAL'",
            "TIME_TYPE": "'UT'",
            "TIME_DIGITS": "'SECONDS'",
            "QUANTITIES": "'2,4,9,18,19,20,21,22,23,24,29'",
            "ANG_FORMAT": "'DEG'",
            "APPARENT": "'AIRLESS'",
            "RANGE_UNITS": "'AU'",
            "CSV_FORMAT": "'YES'",
            "EXTRA_PREC": "'YES'",
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "NightAzimuth/1.1 roadster-ephemeris"},
            follow_redirects=True,
        )
        try:
            response = client.get(_HORIZONS_URL, params=parameters)
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result") if isinstance(payload, dict) else None
            if not isinstance(result, str):
                raise ValueError("Horizons response does not contain a text result")
            fields = parse_horizons_observer_result(result)
            return roadster_from_horizons_fields(fields, when=when)
        finally:
            if owns_client:
                client.close()


def parse_horizons_observer_result(result: str) -> dict[str, str]:
    """Return a normalized header/value mapping for the first Horizons CSV row."""
    lines = result.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == "$$SOE")
        end = next(
            index for index, line in enumerate(lines[start + 1 :], start + 1) if line.strip() == "$$EOE"
        )
    except StopIteration as exc:
        raise ValueError("Horizons ephemeris markers are missing") from exc

    data_line = next((line for line in lines[start + 1 : end] if line.strip()), None)
    if data_line is None:
        raise ValueError("Horizons ephemeris contains no data row")

    header_line = next(
        (
            line
            for line in reversed(lines[:start])
            if "Date" in line and "," in line
        ),
        None,
    )
    if header_line is None:
        raise ValueError("Horizons CSV header is missing")

    headers = [cell.strip() for cell in next(csv.reader([header_line]))]
    values = [cell.strip() for cell in next(csv.reader([data_line]))]
    if len(values) < len(headers):
        values.extend([""] * (len(headers) - len(values)))

    output: dict[str, str] = {}
    duplicate_counts: dict[str, int] = {}
    for header, value in zip(headers, values, strict=False):
        key = _normalise_header(header)
        if not key:
            continue
        count = duplicate_counts.get(key, 0)
        duplicate_counts[key] = count + 1
        output[key if count == 0 else f"{key}_{count + 1}"] = value
    return output


def roadster_from_horizons_fields(
    fields: dict[str, str],
    *,
    when: datetime,
) -> RoadsterEphemeris:
    azimuth = _required_number(fields, "azimuthaapp", "aziaapp")
    elevation = _required_number(fields, "elevationaapp", "elevaapp")
    earth_au = _optional_number(fields, "delta")
    return RoadsterEphemeris(
        id="tesla-roadster-starman",
        name="Tesla Roadster / Starman",
        object_type="Heliocentric artificial object",
        international_designator="2018-017A",
        jpl_target_id=_ROADSTER_TARGET_ID,
        launch_date="2018-02-06",
        launch_vehicle="Falcon Heavy demo mission",
        payload="2008 Tesla Roadster with Starman mannequin",
        body_colour="Red",
        tracking_mode="Predicted ephemeris (not live telemetry)",
        data_source="NASA/JPL Horizons",
        ephemeris_at=_as_utc(when).isoformat(),
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        right_ascension_deg=_optional_number(fields, "raaappar", "raappar"),
        declination_deg=_optional_number(fields, "dec"),
        apparent_magnitude=_optional_number(fields, "apmag"),
        distance_earth_au=earth_au,
        distance_earth_km=earth_au * _AU_KM if earth_au is not None else None,
        distance_sun_au=_optional_number(fields, "r"),
        earth_range_rate_km_s=_optional_number(fields, "deldot"),
        heliocentric_speed_km_s=_optional_number(fields, "vmagsn"),
        observer_relative_speed_km_s=_optional_number(fields, "vmagob"),
        light_time_minutes=_optional_number(fields, "1waydownlt"),
        solar_elongation_deg=_optional_number(fields, "sot"),
        phase_angle_deg=_optional_number(fields, "sto"),
        heliocentric_ecliptic_longitude_deg=_optional_number(fields, "hecllon"),
        heliocentric_ecliptic_latitude_deg=_optional_number(fields, "hecllat"),
        constellation=_optional_text(fields, "cnst", "constellation"),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _find_value(fields: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in fields:
            return fields[name]
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _MISSING_VALUES:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _optional_number(fields: dict[str, str], *names: str) -> float | None:
    return _number(_find_value(fields, *names))


def _required_number(fields: dict[str, str], *names: str) -> float:
    value = _optional_number(fields, *names)
    if value is None:
        raise ValueError(f"Horizons field is missing: {names[0]}")
    return value


def _optional_text(fields: dict[str, str], *names: str) -> str | None:
    value = _find_value(fields, *names)
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _MISSING_VALUES else text
