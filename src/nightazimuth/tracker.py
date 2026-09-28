from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import cos, radians, sin, sqrt
import re
from typing import Any, Iterable

import numpy as np
from sgp4 import omm
from sgp4.api import Satrec, SatrecArray, jday
from skyfield.api import load
from skyfield.sgp4lib import TEME_to_ITRF

from .config import ObserverConfig


_LAUNCH_ID_RE = re.compile(r"^(\d{4}-\d{3})")
_TRACK_OFFSETS_SECONDS = (0, 10, 20, 30, 40, 50, 60)
_WGS84_EQUATORIAL_RADIUS_KM = 6378.137
_WGS84_FLATTENING = 1.0 / 298.257223563


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
        self._observer_itrf_km = self._observer_ecef_km(observer)
        latitude = radians(observer.latitude)
        longitude = radians(observer.longitude)
        self._sin_lat = sin(latitude)
        self._cos_lat = cos(latitude)
        self._sin_lon = sin(longitude)
        self._cos_lon = cos(longitude)

    def positions_above_horizon(
        self,
        elements: Iterable[dict[str, Any]],
        *,
        minimum_elevation_deg: float = 0.0,
        at: datetime | None = None,
    ) -> list[SatellitePosition]:
        """Return every propagated catalogue object above the requested horizon.

        Propagation is deliberately independent of visual brightness.  The full
        ACTIVE catalogue is large, so SGP4 is run as one native batch instead of
        constructing and propagating each EarthSatellite separately in Python.
        """

        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Tracking time must be timezone-aware")

        fields_list: list[dict[str, Any]] = []
        satrecs: list[Satrec] = []
        for fields in elements:
            try:
                satrec = Satrec()
                omm.initialize(satrec, fields)
            except (KeyError, TypeError, ValueError):
                continue
            fields_list.append(fields)
            satrecs.append(satrec)

        if not satrecs:
            return []

        utc_moment = moment.astimezone(timezone.utc)
        track_moments = [
            utc_moment + timedelta(seconds=offset) for offset in _TRACK_OFFSETS_SECONDS
        ]
        skyfield_times = [
            self._timescale.from_datetime(track_moment) for track_moment in track_moments
        ]
        julian_days: list[float] = []
        julian_fractions: list[float] = []
        for track_moment in track_moments:
            jd, fraction = jday(
                track_moment.year,
                track_moment.month,
                track_moment.day,
                track_moment.hour,
                track_moment.minute,
                track_moment.second + track_moment.microsecond / 1_000_000.0,
            )
            julian_days.append(float(jd))
            julian_fractions.append(float(fraction))

        errors, teme_positions, teme_velocities = SatrecArray(satrecs).sgp4(
            np.asarray(julian_days, dtype=float),
            np.asarray(julian_fractions, dtype=float),
        )

        azimuth_series: list[np.ndarray] = []
        elevation_series: list[np.ndarray] = []
        range_series: list[np.ndarray] = []
        for index, skyfield_time in enumerate(skyfield_times):
            r_teme = np.asarray(teme_positions[:, index, :], dtype=float).T
            v_teme = np.asarray(teme_velocities[:, index, :], dtype=float).T
            r_itrf, _v_itrf = TEME_to_ITRF(
                skyfield_time.whole,
                r_teme,
                v_teme,
                0.0,
                0.0,
                skyfield_time.ut1_fraction,
            )
            azimuth, elevation, distance = self._topocentric_angles(np.asarray(r_itrf).T)
            azimuth_series.append(azimuth)
            elevation_series.append(elevation)
            range_series.append(distance)

        current_azimuth = azimuth_series[0]
        current_elevation = elevation_series[0]
        current_range = range_series[0]
        current_errors = np.asarray(errors[:, 0])
        valid = (
            (current_errors == 0)
            & np.isfinite(current_azimuth)
            & np.isfinite(current_elevation)
            & np.isfinite(current_range)
            & (current_elevation >= minimum_elevation_deg)
        )

        results: list[SatellitePosition] = []
        for satellite_index in np.flatnonzero(valid):
            fields = fields_list[int(satellite_index)]
            name = str(fields.get("OBJECT_NAME") or "UNKNOWN")
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
            for track_index, track_moment in enumerate(track_moments):
                if int(errors[satellite_index, track_index]) != 0:
                    continue
                azimuth = float(azimuth_series[track_index][satellite_index])
                elevation = float(elevation_series[track_index][satellite_index])
                distance = float(range_series[track_index][satellite_index])
                if not all(np.isfinite((azimuth, elevation, distance))):
                    continue
                track.append(
                    SatelliteTrackPoint(
                        time_utc=track_moment.isoformat(),
                        azimuth_deg=azimuth,
                        elevation_deg=elevation,
                        range_km=distance,
                    )
                )

            results.append(
                SatellitePosition(
                    name=name,
                    norad_id=norad_id,
                    azimuth_deg=float(current_azimuth[satellite_index]),
                    elevation_deg=float(current_elevation[satellite_index]),
                    range_km=float(current_range[satellite_index]),
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

    def _topocentric_angles(
        self, satellite_itrf_km: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        relative = satellite_itrf_km - self._observer_itrf_km
        x = relative[:, 0]
        y = relative[:, 1]
        z = relative[:, 2]

        east = -self._sin_lon * x + self._cos_lon * y
        north = (
            -self._sin_lat * self._cos_lon * x
            - self._sin_lat * self._sin_lon * y
            + self._cos_lat * z
        )
        up = (
            self._cos_lat * self._cos_lon * x
            + self._cos_lat * self._sin_lon * y
            + self._sin_lat * z
        )
        distance = np.sqrt(east * east + north * north + up * up)
        safe_distance = np.where(distance > 0.0, distance, np.nan)
        elevation = np.degrees(np.arcsin(np.clip(up / safe_distance, -1.0, 1.0)))
        azimuth = (np.degrees(np.arctan2(east, north)) + 360.0) % 360.0
        return azimuth, elevation, distance

    @staticmethod
    def _observer_ecef_km(observer: ObserverConfig) -> np.ndarray:
        latitude = radians(observer.latitude)
        longitude = radians(observer.longitude)
        altitude_km = observer.altitude_m / 1000.0
        flattening = _WGS84_FLATTENING
        eccentricity_squared = flattening * (2.0 - flattening)
        sin_latitude = sin(latitude)
        prime_vertical_radius = _WGS84_EQUATORIAL_RADIUS_KM / sqrt(
            1.0 - eccentricity_squared * sin_latitude * sin_latitude
        )
        x = (prime_vertical_radius + altitude_km) * cos(latitude) * cos(longitude)
        y = (prime_vertical_radius + altitude_km) * cos(latitude) * sin(longitude)
        z = (
            prime_vertical_radius * (1.0 - eccentricity_squared) + altitude_km
        ) * sin_latitude
        return np.asarray((x, y, z), dtype=float)

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
