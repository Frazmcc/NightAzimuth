from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from math import asin, atan2, cos, degrees, radians, sin
from typing import Iterable

from .aircraft import AircraftObservation

EARTH_RADIUS_M = 6_371_000.0


class AircraftPositionState(StrEnum):
    MEASURED = "measured"
    INTERPOLATED = "interpolated"
    EXTRAPOLATED = "extrapolated"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ResolvedAircraftPosition:
    icao24: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float | None
    track_deg: float | None
    ground_speed_mps: float | None
    vertical_rate_mps: float | None
    resolved_at: datetime
    source_observed_at: datetime
    state: AircraftPositionState


class AircraftMotionHistory:
    """Bounded per-aircraft observation history with interpolation and short prediction."""

    def __init__(
        self,
        *,
        max_fixes_per_aircraft: int = 8,
        max_history_age_seconds: float = 120.0,
        prediction_limit_seconds: float = 15.0,
    ) -> None:
        if max_fixes_per_aircraft < 2:
            raise ValueError("max_fixes_per_aircraft must be at least 2")
        if max_history_age_seconds <= 0:
            raise ValueError("max_history_age_seconds must be positive")
        if prediction_limit_seconds < 0:
            raise ValueError("prediction_limit_seconds must be non-negative")
        self._max_fixes = max_fixes_per_aircraft
        self._max_age = timedelta(seconds=max_history_age_seconds)
        self._prediction_limit = timedelta(seconds=prediction_limit_seconds)
        self._history: dict[str, list[AircraftObservation]] = {}

    def add(self, observation: AircraftObservation) -> None:
        fixes = self._history.setdefault(observation.icao24, [])
        timestamp = observation.position_observed_at

        for index, existing in enumerate(fixes):
            if existing.position_observed_at == timestamp:
                fixes[index] = observation
                break
        else:
            if fixes and timestamp < fixes[-1].position_observed_at:
                return
            fixes.append(observation)

        newest = fixes[-1].position_observed_at
        cutoff = newest - self._max_age
        fixes[:] = [fix for fix in fixes if fix.position_observed_at >= cutoff]
        if len(fixes) > self._max_fixes:
            del fixes[:-self._max_fixes]

    def extend(self, observations: Iterable[AircraftObservation]) -> None:
        for observation in observations:
            self.add(observation)

    def clear(self) -> None:
        self._history.clear()

    def clear_aircraft(self, icao24: str) -> None:
        self._history.pop(icao24.strip().lower(), None)

    def resolve(
        self,
        icao24: str,
        at: datetime | None = None,
    ) -> ResolvedAircraftPosition | None:
        target = _utc(at)
        fixes = self._history.get(icao24.strip().lower())
        if not fixes:
            return None

        for fix in fixes:
            if fix.position_observed_at == target:
                return _from_observation(fix, target, AircraftPositionState.MEASURED)

        for first, second in zip(fixes, fixes[1:]):
            if first.position_observed_at <= target <= second.position_observed_at:
                span = (second.position_observed_at - first.position_observed_at).total_seconds()
                if span <= 0:
                    return _from_observation(second, target, AircraftPositionState.MEASURED)
                fraction = (target - first.position_observed_at).total_seconds() / span
                return _interpolate(first, second, fraction, target)

        latest = fixes[-1]
        if target < fixes[0].position_observed_at:
            return None

        ahead = target - latest.position_observed_at
        if ahead > self._prediction_limit:
            return _from_observation(latest, target, AircraftPositionState.STALE)
        if ahead <= timedelta(0):
            return _from_observation(latest, target, AircraftPositionState.MEASURED)
        return _extrapolate(latest, target)


def _interpolate(
    first: AircraftObservation,
    second: AircraftObservation,
    fraction: float,
    target: datetime,
) -> ResolvedAircraftPosition:
    lat = first.latitude_deg + (second.latitude_deg - first.latitude_deg) * fraction
    lon = _interpolate_longitude(first.longitude_deg, second.longitude_deg, fraction)
    altitude = _interpolate_optional(first.preferred_altitude_m, second.preferred_altitude_m, fraction)
    speed = _interpolate_optional(first.ground_speed_mps, second.ground_speed_mps, fraction)
    vertical_rate = _interpolate_optional(first.vertical_rate_mps, second.vertical_rate_mps, fraction)
    track = _interpolate_angle(first.track_deg, second.track_deg, fraction)
    return ResolvedAircraftPosition(
        icao24=second.icao24,
        latitude_deg=lat,
        longitude_deg=lon,
        altitude_m=altitude,
        track_deg=track,
        ground_speed_mps=speed,
        vertical_rate_mps=vertical_rate,
        resolved_at=target,
        source_observed_at=second.position_observed_at,
        state=AircraftPositionState.INTERPOLATED,
    )


def _extrapolate(
    latest: AircraftObservation,
    target: datetime,
) -> ResolvedAircraftPosition:
    seconds = max(0.0, (target - latest.position_observed_at).total_seconds())
    latitude = latest.latitude_deg
    longitude = latest.longitude_deg

    if latest.ground_speed_mps is not None and latest.track_deg is not None:
        distance_m = latest.ground_speed_mps * seconds
        latitude, longitude = _destination_point(
            latest.latitude_deg,
            latest.longitude_deg,
            latest.track_deg,
            distance_m,
        )

    altitude = latest.preferred_altitude_m
    if altitude is not None and latest.vertical_rate_mps is not None:
        altitude += latest.vertical_rate_mps * seconds

    return ResolvedAircraftPosition(
        icao24=latest.icao24,
        latitude_deg=latitude,
        longitude_deg=longitude,
        altitude_m=altitude,
        track_deg=latest.track_deg,
        ground_speed_mps=latest.ground_speed_mps,
        vertical_rate_mps=latest.vertical_rate_mps,
        resolved_at=target,
        source_observed_at=latest.position_observed_at,
        state=AircraftPositionState.EXTRAPOLATED,
    )


def _from_observation(
    observation: AircraftObservation,
    target: datetime,
    state: AircraftPositionState,
) -> ResolvedAircraftPosition:
    return ResolvedAircraftPosition(
        icao24=observation.icao24,
        latitude_deg=observation.latitude_deg,
        longitude_deg=observation.longitude_deg,
        altitude_m=observation.preferred_altitude_m,
        track_deg=observation.track_deg,
        ground_speed_mps=observation.ground_speed_mps,
        vertical_rate_mps=observation.vertical_rate_mps,
        resolved_at=target,
        source_observed_at=observation.position_observed_at,
        state=state,
    )


def _interpolate_optional(first: float | None, second: float | None, fraction: float) -> float | None:
    if first is None and second is None:
        return None
    if first is None:
        return second
    if second is None:
        return first
    return first + (second - first) * fraction


def _interpolate_angle(first: float | None, second: float | None, fraction: float) -> float | None:
    if first is None and second is None:
        return None
    if first is None:
        return second
    if second is None:
        return first
    delta = (second - first + 180.0) % 360.0 - 180.0
    return (first + delta * fraction) % 360.0


def _interpolate_longitude(first: float, second: float, fraction: float) -> float:
    delta = (second - first + 180.0) % 360.0 - 180.0
    return (first + delta * fraction + 180.0) % 360.0 - 180.0


def _destination_point(
    latitude_deg: float,
    longitude_deg: float,
    bearing_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    bearing = radians(bearing_deg)
    angular_distance = distance_m / EARTH_RADIUS_M

    target_latitude = asin(
        sin(latitude) * cos(angular_distance)
        + cos(latitude) * sin(angular_distance) * cos(bearing)
    )
    target_longitude = longitude + atan2(
        sin(bearing) * sin(angular_distance) * cos(latitude),
        cos(angular_distance) - sin(latitude) * sin(target_latitude),
    )
    return degrees(target_latitude), (degrees(target_longitude) + 540.0) % 360.0 - 180.0


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("motion resolution time must be timezone-aware")
    return value.astimezone(timezone.utc)
