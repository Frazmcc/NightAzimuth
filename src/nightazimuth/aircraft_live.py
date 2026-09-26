from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .aircraft import AircraftObserver, AircraftSnapshot
from .aircraft_geometry import resolved_aircraft_sky_position
from .aircraft_motion import AircraftMotionHistory, AircraftPositionState
from .aircraft_squawk import SquawkAlert, classify_squawk


@dataclass(frozen=True, slots=True)
class AircraftSkyTrackPoint:
    seconds_from_now: float
    azimuth_deg: float
    elevation_deg: float


@dataclass(frozen=True, slots=True)
class SkyAircraft:
    icao24: str
    callsign: str | None
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    altitude_m: float
    track_deg: float | None
    ground_speed_mps: float | None
    vertical_rate_mps: float | None
    squawk: str | None
    squawk_alert: SquawkAlert | None
    position_state: AircraftPositionState
    position_age_seconds: float
    source_id: str
    source_label: str
    registration: str | None = None
    type_code: str | None = None
    type_description: str | None = None
    operator: str | None = None
    military: bool = False
    latitude_deg: float | None = None
    longitude_deg: float | None = None
    future_track: tuple[AircraftSkyTrackPoint, ...] = ()


def build_sky_aircraft(
    snapshot: AircraftSnapshot,
    observer: AircraftObserver,
    history: AircraftMotionHistory,
    *,
    at: datetime | None = None,
    minimum_elevation_deg: float = 0.0,
    include_ground: bool = False,
    include_stale: bool = False,
    maximum_position_age_seconds: float | None = None,
    projection_seconds: tuple[float, ...] = (5.0, 10.0, 15.0),
) -> list[SkyAircraft]:
    moment = _utc(at)
    if maximum_position_age_seconds is not None and maximum_position_age_seconds <= 0:
        raise ValueError("maximum_position_age_seconds must be positive when supplied")

    history.extend(snapshot.observations)
    contacts: list[SkyAircraft] = []
    for observation in snapshot.observations:
        if observation.on_ground and not include_ground:
            continue

        position_age_seconds = observation.position_age_seconds(moment)
        if (
            maximum_position_age_seconds is not None
            and position_age_seconds > maximum_position_age_seconds
        ):
            continue

        resolved = history.resolve(observation.icao24, moment)
        if resolved is None or (resolved.state == AircraftPositionState.STALE and not include_stale):
            continue
        sky = resolved_aircraft_sky_position(observer, resolved)
        if sky is None or sky.elevation_deg < minimum_elevation_deg:
            continue
        track_points = [AircraftSkyTrackPoint(0.0, sky.azimuth_deg, sky.elevation_deg)]
        for seconds in projection_seconds:
            if seconds <= 0:
                continue
            projected = history.resolve(observation.icao24, moment + timedelta(seconds=float(seconds)))
            if projected is None or projected.state == AircraftPositionState.STALE:
                break
            projected_sky = resolved_aircraft_sky_position(observer, projected)
            if projected_sky is None:
                break
            track_points.append(
                AircraftSkyTrackPoint(
                    float(seconds), projected_sky.azimuth_deg, projected_sky.elevation_deg
                )
            )
        contacts.append(
            SkyAircraft(
                icao24=observation.icao24,
                callsign=observation.callsign,
                azimuth_deg=sky.azimuth_deg,
                elevation_deg=sky.elevation_deg,
                range_km=sky.slant_range_m / 1000.0,
                altitude_m=sky.altitude_m,
                track_deg=resolved.track_deg,
                ground_speed_mps=resolved.ground_speed_mps,
                vertical_rate_mps=resolved.vertical_rate_mps,
                squawk=observation.squawk,
                squawk_alert=classify_squawk(observation.squawk),
                position_state=resolved.state,
                position_age_seconds=max(
                    0.0, (moment - resolved.source_observed_at).total_seconds()
                ),
                source_id=snapshot.source_id,
                source_label=snapshot.source_label,
                registration=observation.registration,
                type_code=observation.type_code,
                type_description=observation.type_description,
                operator=observation.operator,
                military=observation.military,
                latitude_deg=resolved.latitude_deg,
                longitude_deg=resolved.longitude_deg,
                future_track=tuple(track_points),
            )
        )
    return sorted(
        contacts,
        key=lambda contact: (
            -(contact.squawk_alert.priority if contact.squawk_alert is not None else 0),
            -int(contact.military),
            -contact.elevation_deg,
            contact.range_km,
            contact.icao24,
        ),
    )


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aircraft live-view time must be timezone-aware")
    return value.astimezone(timezone.utc)
