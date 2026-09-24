from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx

from .config import ObserverConfig

MET_NO_LOCATIONFORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
MET_NO_USER_AGENT = "NightAzimuth/1.0 (+https://github.com/Frazmcc/NightAzimuth)"


class WeatherProviderError(RuntimeError):
    """Raised when weather data cannot be loaded from the provider or cache."""


@dataclass(frozen=True, slots=True)
class WeatherPoint:
    time_utc: datetime
    air_temperature_c: float | None
    relative_humidity_percent: float | None
    cloud_total_percent: float | None
    cloud_low_percent: float | None
    cloud_medium_percent: float | None
    cloud_high_percent: float | None
    fog_percent: float | None
    wind_speed_m_s: float | None
    wind_from_direction_deg: float | None
    precipitation_next_hour_mm: float | None


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    source_name: str
    fetched_at_utc: datetime
    source_updated_at_utc: datetime | None
    points: tuple[WeatherPoint, ...]
    from_cache: bool = False
    fallback_used: bool = False

    def current_or_next(self, at: datetime | None = None) -> WeatherPoint | None:
        if not self.points:
            return None
        moment = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        future = [point for point in self.points if point.time_utc >= moment]
        return future[0] if future else self.points[-1]

    def next_points(self, count: int = 4, at: datetime | None = None) -> tuple[WeatherPoint, ...]:
        if count <= 0:
            return ()
        moment = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        future = [point for point in self.points if point.time_utc >= moment]
        return tuple(future[:count])

    def source_age(self, at: datetime | None = None) -> timedelta | None:
        if self.source_updated_at_utc is None:
            return None
        moment = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return max(timedelta(0), moment - self.source_updated_at_utc)


class WeatherProvider(Protocol):
    def load(self, observer: ObserverConfig) -> WeatherSnapshot: ...


class MetNorwayWeatherProvider:
    """Zero-cost point forecast backed by MET Norway Locationforecast 2.0."""

    def __init__(
        self,
        *,
        cache_directory: Path,
        cache_max_age_minutes: int = 30,
        timeout_seconds: float = 30.0,
        cache_max_files: int = 256,
    ) -> None:
        self.cache_directory = Path(cache_directory) / "weather"
        self.cache_max_age_minutes = cache_max_age_minutes
        self.timeout_seconds = timeout_seconds
        self.cache_max_files = max(1, cache_max_files)

    def load(self, observer: ObserverConfig) -> WeatherSnapshot:
        cache_path = self._cache_path(observer)
        if self._cache_is_fresh(cache_path):
            return self._read_cache(cache_path, from_cache=True, fallback_used=False)
        try:
            payload = self._download(observer)
            snapshot = parse_met_no_locationforecast(payload, fetched_at_utc=datetime.now(timezone.utc))
            self._write_cache(cache_path, payload)
            try:
                self._prune_cache(keep=cache_path)
            except OSError:
                # Cache maintenance must not discard an otherwise valid provider response.
                pass
            return snapshot
        except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            if cache_path.exists():
                return self._read_cache(cache_path, from_cache=True, fallback_used=True)
            raise WeatherProviderError(f"Unable to load MET Norway weather data: {exc}") from exc

    def _download(self, observer: ObserverConfig) -> dict[str, Any]:
        response = httpx.get(
            MET_NO_LOCATIONFORECAST_URL,
            params={
                "lat": f"{observer.latitude:.5f}",
                "lon": f"{observer.longitude:.5f}",
                "altitude": f"{observer.altitude_m:.0f}",
            },
            headers={"User-Agent": MET_NO_USER_AGENT, "Accept": "application/json"},
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("MET Norway returned an unexpected JSON structure")
        return payload

    def _cache_path(self, observer: ObserverConfig) -> Path:
        key = f"{observer.latitude:.5f},{observer.longitude:.5f},{observer.altitude_m:.0f}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self.cache_directory / f"met_no_{digest}.json"

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age = datetime.now(timezone.utc) - modified
        return age.total_seconds() <= self.cache_max_age_minutes * 60

    def _read_cache(
        self, path: Path, *, from_cache: bool, fallback_used: bool = False
    ) -> WeatherSnapshot:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise WeatherProviderError(f"Invalid weather cache: {path}")
        fetched = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        snapshot = parse_met_no_locationforecast(payload, fetched_at_utc=fetched)
        return WeatherSnapshot(
            source_name=snapshot.source_name,
            fetched_at_utc=snapshot.fetched_at_utc,
            source_updated_at_utc=snapshot.source_updated_at_utc,
            points=snapshot.points,
            from_cache=from_cache,
            fallback_used=fallback_used,
        )

    def _prune_cache(self, *, keep: Path) -> None:
        files = [path for path in self.cache_directory.glob("met_no_*.json") if path != keep]
        excess = len(files) + 1 - self.cache_max_files
        if excess <= 0:
            return
        files.sort(key=lambda path: path.stat().st_mtime)
        for path in files[:excess]:
            path.unlink(missing_ok=True)

    @staticmethod
    def _write_cache(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle)
            temp_path = Path(handle.name)
        try:
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


def parse_met_no_locationforecast(
    payload: dict[str, Any],
    *,
    fetched_at_utc: datetime,
) -> WeatherSnapshot:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Weather response is missing properties")
    meta = properties.get("meta")
    updated_at = None
    if isinstance(meta, dict) and meta.get("updated_at"):
        updated_at = _parse_datetime(str(meta["updated_at"]))
    timeseries = properties.get("timeseries")
    if not isinstance(timeseries, list):
        raise ValueError("Weather response is missing timeseries")

    points: list[WeatherPoint] = []
    for entry in timeseries:
        if not isinstance(entry, dict):
            continue
        raw_time = entry.get("time")
        data = entry.get("data")
        if not raw_time or not isinstance(data, dict):
            continue
        instant = data.get("instant")
        details = instant.get("details") if isinstance(instant, dict) else {}
        if not isinstance(details, dict):
            details = {}
        next_1 = data.get("next_1_hours")
        next_1_details = next_1.get("details") if isinstance(next_1, dict) else {}
        if not isinstance(next_1_details, dict):
            next_1_details = {}
        points.append(
            WeatherPoint(
                time_utc=_parse_datetime(str(raw_time)),
                air_temperature_c=_float_or_none(details.get("air_temperature")),
                relative_humidity_percent=_float_or_none(details.get("relative_humidity")),
                cloud_total_percent=_float_or_none(details.get("cloud_area_fraction")),
                cloud_low_percent=_float_or_none(details.get("cloud_area_fraction_low")),
                cloud_medium_percent=_float_or_none(details.get("cloud_area_fraction_medium")),
                cloud_high_percent=_float_or_none(details.get("cloud_area_fraction_high")),
                fog_percent=_float_or_none(details.get("fog_area_fraction")),
                wind_speed_m_s=_float_or_none(details.get("wind_speed")),
                wind_from_direction_deg=_float_or_none(details.get("wind_from_direction")),
                precipitation_next_hour_mm=_float_or_none(next_1_details.get("precipitation_amount")),
            )
        )
    if not points:
        raise ValueError("Weather response contained no usable forecast points")
    points.sort(key=lambda point: point.time_utc)
    return WeatherSnapshot(
        source_name="MET Norway Locationforecast 2.0",
        fetched_at_utc=fetched_at_utc.astimezone(timezone.utc),
        source_updated_at_utc=updated_at,
        points=tuple(points),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Weather timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
