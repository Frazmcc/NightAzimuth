from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from skyfield.api import Loader, wgs84

from .config import ObserverConfig
from .weather import WeatherPoint, WeatherSnapshot


_RESOURCE_LOCK = Lock()
_SHARED_RESOURCES: dict[str, tuple[object, object, object, object]] = {}


def _astronomy_resources(cache_directory: Path) -> tuple[object, object, object, object]:
    """Load immutable Skyfield resources once per cache directory and process."""
    key = str(Path(cache_directory).resolve())
    with _RESOURCE_LOCK:
        resources = _SHARED_RESOURCES.get(key)
        if resources is None:
            loader = Loader(str(Path(cache_directory) / "skyfield"), verbose=False)
            timescale = loader.timescale()
            ephemeris = loader("de421.bsp")
            resources = (timescale, ephemeris, ephemeris["earth"], ephemeris["sun"])
            _SHARED_RESOURCES[key] = resources
        return resources


@dataclass(frozen=True, slots=True)
class ViewingGuidance:
    time_utc: datetime
    rating: str
    confidence: str
    sun_altitude_deg: float
    cloud_percent: float | None
    fog_percent: float | None
    precipitation_mm: float | None
    reasons: tuple[str, ...]


class ObservingPlanner:
    """Build transparent observing guidance from astronomy + point weather."""

    def __init__(self, observer: ObserverConfig, *, cache_directory: Path) -> None:
        self.observer = observer
        (
            self._timescale,
            self._ephemeris,
            self._earth,
            self._sun,
        ) = _astronomy_resources(cache_directory)
        self._location = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )

    def build(
        self,
        weather: WeatherSnapshot,
        *,
        hours: int = 24,
        now_utc: datetime | None = None,
    ) -> tuple[ViewingGuidance, ...]:
        moment = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
        horizon = moment + timedelta(hours=max(1, hours))
        points = [
            point
            for point in weather.points
            if moment <= point.time_utc <= horizon
        ]
        return tuple(self._guidance_for_point(point, moment) for point in points)

    def _guidance_for_point(self, point: WeatherPoint, now_utc: datetime) -> ViewingGuidance:
        sun_altitude = self._sun_altitude(point.time_utc)
        score = 100.0
        reasons: list[str] = []

        if sun_altitude > -0.833:
            score -= 75.0
            reasons.append("daylight/sunset not complete")
        elif sun_altitude > -6.0:
            score -= 45.0
            reasons.append("civil twilight")
        elif sun_altitude > -12.0:
            score -= 25.0
            reasons.append("nautical twilight")
        elif sun_altitude > -18.0:
            score -= 12.0
            reasons.append("astronomical twilight")
        else:
            reasons.append("astronomically dark")

        cloud = _bounded_percent(point.cloud_total_percent)
        if cloud is not None:
            score -= cloud * 0.62
            reasons.append(f"{cloud:.0f}% forecast cloud")
        else:
            reasons.append("cloud forecast unavailable")

        fog = _bounded_percent(point.fog_percent)
        if fog is not None:
            score -= fog * 0.25
            if fog >= 10.0:
                reasons.append(f"{fog:.0f}% fog fraction")

        precipitation = point.precipitation_next_hour_mm
        if precipitation is not None and precipitation > 0.0:
            score -= min(30.0, 10.0 + precipitation * 8.0)
            reasons.append(f"{precipitation:.1f} mm precipitation next hour")

        score = max(0.0, min(100.0, score))
        rating = _rating(score)
        horizon_hours = max(0.0, (point.time_utc - now_utc).total_seconds() / 3600.0)
        confidence = _confidence(horizon_hours)
        return ViewingGuidance(
            time_utc=point.time_utc,
            rating=rating,
            confidence=confidence,
            sun_altitude_deg=sun_altitude,
            cloud_percent=cloud,
            fog_percent=fog,
            precipitation_mm=precipitation,
            reasons=tuple(reasons),
        )

    def _sun_altitude(self, moment: datetime) -> float:
        t = self._timescale.from_datetime(moment.astimezone(timezone.utc))
        apparent = (self._earth + self._location).at(t).observe(self._sun).apparent()
        altitude, _, _ = apparent.altaz()
        return float(altitude.degrees)


def _bounded_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, float(value)))


def _rating(score: float) -> str:
    if score >= 78.0:
        return "Very good"
    if score >= 58.0:
        return "Good"
    if score >= 38.0:
        return "Fair"
    return "Poor"


def _confidence(hours_ahead: float) -> str:
    if hours_ahead <= 6.0:
        return "High"
    if hours_ahead <= 12.0:
        return "Moderate-high"
    if hours_ahead <= 18.0:
        return "Moderate"
    if hours_ahead <= 24.0:
        return "Lower"
    if hours_ahead <= 48.0:
        return "Low"
    return "Very low"
