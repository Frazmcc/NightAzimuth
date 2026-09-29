from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from math import cos, radians, sin, sqrt
import re
import threading
from time import perf_counter
from typing import Any, Iterable

import numpy as np
from sgp4 import omm
from sgp4.api import Satrec, SatrecArray, jday
from skyfield.api import load
from skyfield.functions import mxv, rot_z
from skyfield.sgp4lib import theta_GMST1982

from .config import ObserverConfig


_LAUNCH_ID_RE = re.compile(r"^(\d{4}-\d{3})")
_TRACK_OFFSETS_SECONDS = (0, 10, 20, 30, 40, 50, 60)
_WGS84_EQUATORIAL_RADIUS_KM = 6378.137
_WGS84_FLATTENING = 1.0 / 298.257223563
_PREPARED_CATALOGUE_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class _PreparedCatalogue:
    cache_key: object
    element_count: int
    valid_indices: tuple[int, ...]
    satrecs: tuple[Satrec, ...]


_PREPARED_CATALOGUE: _PreparedCatalogue | None = None


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


def _catalogue_fingerprint(elements: list[dict[str, Any]]) -> bytes:
    """Hash orbital content for callers that cannot supply a generation key."""

    digest = hashlib.sha256()
    for fields in elements:
        orbital_fields = {
            key: value for key, value in fields.items() if key != "_nightazimuth_groups"
        }
        encoded = json.dumps(
            orbital_fields,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(4, byteorder="big", signed=False))
        digest.update(encoded)
    return digest.digest()


def _build_prepared_catalogue(
    elements: list[dict[str, Any]],
    cache_key: object,
) -> _PreparedCatalogue:
    valid_indices: list[int] = []
    satrecs: list[Satrec] = []
    for index, fields in enumerate(elements):
        try:
            satrec = Satrec()
            omm.initialize(satrec, fields)
        except (KeyError, TypeError, ValueError):
            continue
        valid_indices.append(index)
        satrecs.append(satrec)

    return _PreparedCatalogue(
        cache_key=cache_key,
        element_count=len(elements),
        valid_indices=tuple(valid_indices),
        satrecs=tuple(satrecs),
    )


def _prepared_catalogue_for(
    elements: list[dict[str, Any]],
    cache_key: object | None = None,
) -> tuple[_PreparedCatalogue, bool]:
    """Return the one cached Satrec generation, replacing it when data changes."""

    global _PREPARED_CATALOGUE

    resolved_key: object
    if cache_key is None:
        resolved_key = ("sha256", _catalogue_fingerprint(elements))
    else:
        resolved_key = ("generation", cache_key)

    with _PREPARED_CATALOGUE_LOCK:
        cached = _PREPARED_CATALOGUE
        if (
            cached is not None
            and cached.element_count == len(elements)
            and cached.cache_key == resolved_key
        ):
            return cached, True

        prepared = _build_prepared_catalogue(elements, resolved_key)
        _PREPARED_CATALOGUE = prepared
        return prepared, False


def _clear_prepared_catalogue_cache() -> None:
    """Clear the single prepared Satrec generation (primarily for tests)."""

    global _PREPARED_CATALOGUE
    with _PREPARED_CATALOGUE_LOCK:
        _PREPARED_CATALOGUE = None


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
        self.last_timings: dict[str, float] = {}

    def positions_above_horizon(
        self,
        elements: Iterable[dict[str, Any]],
        *,
        minimum_elevation_deg: float = 0.0,
        at: datetime | None = None,
        catalogue_cache_key: object | None = None,
    ) -> list[SatellitePosition]:
        """Return every propagated catalogue object above the requested horizon.

        Propagation is deliberately independent of visual brightness. The full
        ACTIVE catalogue is large, so current positions are propagated as one
        native batch. Future track points are then propagated only for satellites
        that are visible at the current instant. The immutable OMM-to-Satrec
        conversion is cached for one catalogue generation while current-time
        propagation is still performed on every request. Hosted callers can
        supply a cheap catalogue generation key; other callers fall back to a
        content hash. Internal stage timings are retained on ``last_timings`` for
        diagnostics.
        """

        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Tracking time must be timezone-aware")

        self.last_timings = {}
        prepare_started = perf_counter()
        element_list = list(elements)
        prepared, cache_hit = _prepared_catalogue_for(
            element_list,
            cache_key=catalogue_cache_key,
        )
        fields_list = [element_list[index] for index in prepared.valid_indices]
        satrecs = prepared.satrecs
        self.last_timings["prepare_cache_hit"] = 1.0 if cache_hit else 0.0

        if not satrecs:
            self.last_timings["prepare_ms"] = (perf_counter() - prepare_started) * 1000.0
            self.last_timings["propagation_ms"] = 0.0
            self.last_timings["track_build_ms"] = 0.0
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
        self.last_timings["prepare_ms"] = (perf_counter() - prepare_started) * 1000.0

        propagation_started = perf_counter()

        # Every catalogue object must be propagated for the current instant so
        # the visibility filter remains exact. Only satellites that pass that
        # filter need the six future SGP4 points used for their on-screen tracks.
        current_errors_matrix, current_teme_positions, _current_teme_velocities = SatrecArray(
            list(satrecs)
        ).sgp4(
            np.asarray(julian_days[:1], dtype=float),
            np.asarray(julian_fractions[:1], dtype=float),
        )
        current_errors = np.asarray(current_errors_matrix[:, 0])
        current_r_teme = np.asarray(current_teme_positions[:, 0, :], dtype=float).T
        current_theta, _current_theta_dot = theta_GMST1982(
            skyfield_times[0].whole,
            skyfield_times[0].ut1_fraction,
        )
        current_r_itrf = mxv(rot_z(-current_theta), current_r_teme)
        current_azimuth, current_elevation, current_range = self._topocentric_angles(
            np.asarray(current_r_itrf).T
        )
        valid = (
            (current_errors == 0)
            & np.isfinite(current_azimuth)
            & np.isfinite(current_elevation)
            & np.isfinite(current_range)
            & (current_elevation >= minimum_elevation_deg)
        )
        visible_indices = np.flatnonzero(valid)

        future_errors = np.empty((0, len(track_moments) - 1), dtype=int)
        future_azimuth_series: list[np.ndarray] = []
        future_elevation_series: list[np.ndarray] = []
        future_range_series: list[np.ndarray] = []

        if visible_indices.size:
            visible_satrecs = [satrecs[int(index)] for index in visible_indices]
            future_errors, future_teme_positions, _future_teme_velocities = SatrecArray(
                visible_satrecs
            ).sgp4(
                np.asarray(julian_days[1:], dtype=float),
                np.asarray(julian_fractions[1:], dtype=float),
            )

            for future_index, skyfield_time in enumerate(skyfield_times[1:]):
                # Skyfield's TEME_to_ITRF() helper also computes velocity and its
                # scalar angular-velocity cross-product does not broadcast over a
                # satellite matrix. For position we need only the identical PEF/
                # ITRF z-rotation (xp=yp=0), which mxv handles natively in batch.
                r_teme = np.asarray(
                    future_teme_positions[:, future_index, :], dtype=float
                ).T
                theta, _theta_dot = theta_GMST1982(
                    skyfield_time.whole,
                    skyfield_time.ut1_fraction,
                )
                r_itrf = mxv(rot_z(-theta), r_teme)
                azimuth, elevation, distance = self._topocentric_angles(
                    np.asarray(r_itrf).T
                )
                future_azimuth_series.append(azimuth)
                future_elevation_series.append(elevation)
                future_range_series.append(distance)

        self.last_timings["propagation_ms"] = (perf_counter() - propagation_started) * 1000.0

        track_build_started = perf_counter()
        results: list[SatellitePosition] = []
        for visible_offset, satellite_index_raw in enumerate(visible_indices):
            satellite_index = int(satellite_index_raw)
            fields = fields_list[satellite_index]
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

            track: list[SatelliteTrackPoint] = [
                SatelliteTrackPoint(
                    time_utc=track_moments[0].isoformat(),
                    azimuth_deg=float(current_azimuth[satellite_index]),
                    elevation_deg=float(current_elevation[satellite_index]),
                    range_km=float(current_range[satellite_index]),
                )
            ]
            for future_index, track_moment in enumerate(track_moments[1:]):
                if int(future_errors[visible_offset, future_index]) != 0:
                    continue
                azimuth = float(future_azimuth_series[future_index][visible_offset])
                elevation = float(future_elevation_series[future_index][visible_offset])
                distance = float(future_range_series[future_index][visible_offset])
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

        sorted_results = sorted(results, key=lambda item: item.elevation_deg, reverse=True)
        self.last_timings["track_build_ms"] = (perf_counter() - track_build_started) * 1000.0
        return sorted_results

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
