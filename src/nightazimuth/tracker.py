from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Iterable

from skyfield.api import EarthSatellite, load, wgs84

from .config import ObserverConfig


_LAUNCH_ID_RE = re.compile(r"^(\d{4}-\d{3})")
_TRACK_OFFSETS_SECONDS = (0, 10, 20, 30, 40, 50, 60)


@dataclass(frozen=True, slots=True)
class SatelliteTrackPoint:
    time_utc: str
    azimuth_deg: float
    elevation_deg: float
    range_km: float


@dataclass(frozen=True, slots=True)
class SatellitePosition:
    name: str
    norad_id: str
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    object_id: str | None = None
    launch_id: str | None = None
    category: str = "Satellite"
    source_groups: tuple[str, ...] = ()
    epoch_utc: str | None = None
    inclination_deg: float | None = None
    period_minutes: float | None = None
    eccentricity: float | None = None
    track: tuple[SatelliteTrackPoint, ...] = ()


class SatelliteTracker:
    def __init__(self, observer: ObserverConfig) -> None:
        self.observer = observer
        self._timescale = load.timescale()
        self._observer_position = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )

    def positions_above_horizon(
        self,
        elements: Iterable[dict[str, Any]],
        *,
        minimum_elevation_deg: float = 0.0,
        at: datetime | None = None,
    ) -> list[SatellitePosition]:
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Tracking time must be timezone-aware")

        utc_moment = moment.astimezone(timezone.utc)
        track_moments = [utc_moment + timedelta(seconds=offset) for offset in _TRACK_OFFSETS_SECONDS]
        track_times = [self._timescale.from_datetime(track_moment) for track_moment in track_moments]
        results: list[SatellitePosition] = []

        for fields in elements:
            satellite = EarthSatellite.from_omm(self._timescale, fields)
            difference = satellite - self._observer_position
            topocentric = difference.at(track_times[0])
            altitude, azimuth, distance = topocentric.altaz()

            elevation_deg = float(altitude.degrees)
            if elevation_deg < minimum_elevation_deg:
                continue

            name = str(fields.get("OBJECT_NAME") or satellite.name or "UNKNOWN")
            norad_id = str(fields.get("NORAD_CAT_ID") or "")
            object_id_raw = fields.get("OBJECT_ID")
            object_id = str(object_id_raw).strip() if object_id_raw else None
            launch_match = _LAUNCH_ID_RE.match(object_id or "")
            launch_id = launch_match.group(1) if launch_match else None
            source_groups = tuple(str(group) for group in fields.get("_nightazimuth_groups", ()))
            category = self._category_for(name, source_groups)
            mean_motion = self._optional_float(fields.get("MEAN_MOTION"))
            period_minutes = 1440.0 / mean_motion if mean_motion and mean_motion > 0 else None

            track: list[SatelliteTrackPoint] = []
            for track_moment, track_time in zip(track_moments, track_times, strict=True):
                point = difference.at(track_time)
                point_altitude, point_azimuth, point_distance = point.altaz()
                track.append(
                    SatelliteTrackPoint(
                        time_utc=track_moment.isoformat(),
                        azimuth_deg=float(point_azimuth.degrees) % 360.0,
                        elevation_deg=float(point_altitude.degrees),
                        range_km=float(point_distance.km),
                    )
                )

            results.append(
                SatellitePosition(
                    name=name,
                    norad_id=norad_id,
                    azimuth_deg=float(azimuth.degrees) % 360.0,
                    elevation_deg=elevation_deg,
                    range_km=float(distance.km),
                    object_id=object_id,
                    launch_id=launch_id,
                    category=category,
                    source_groups=source_groups,
                    epoch_utc=str(fields.get("EPOCH")) if fields.get("EPOCH") else None,
                    inclination_deg=self._optional_float(fields.get("INCLINATION")),
                    period_minutes=period_minutes,
                    eccentricity=self._optional_float(fields.get("ECCENTRICITY")),
                    track=tuple(track),
                )
            )

        return sorted(results, key=lambda item: item.elevation_deg, reverse=True)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _category_for(name: str, source_groups: tuple[str, ...]) -> str:
        if name.upper().startswith("STARLINK"):
            return "Starlink"
        if "LAST-30-DAYS" in source_groups:
            return "Recent launch"
        if "STATIONS" in source_groups:
            return "Space station"
        if "VISUAL" in source_groups:
            return "Bright satellite"
        return "Satellite"
