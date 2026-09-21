from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .aircraft import AircraftObserver, AircraftSnapshot
from .aircraft_geometry import resolved_aircraft_sky_position
from .aircraft_motion import AircraftMotionHistory, AircraftPositionState


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
    position_state: AircraftPositionState
    position_age_seconds: float
    source_id: str
    source_label: str


def build_sky_aircraft(
    snapshot: AircraftSnapshot,
    observer: AircraftObserver,
    history: AircraftMotionHistory,
    *,
    at: datetime | None = None,
    minimum_elevation_deg: float = 0.0,
    include_ground: bool = False,
    include_stale: bool = False,
) -> list[SkyAircraft]:
    """Convert one authoritative aircraft snapshot into Live-Finder-ready contacts."""
    moment = _utc(at)
    history.extend(snapshot.observations)
    contacts: list[SkyAircraft] = []

    for observation in snapshot.observations:
        if observation.on_ground and not include_ground:
            continue

        resolved = history.resolve(observation.icao24, moment)
        if resolved is None:
            continue
        if resolved.state == AircraftPositionState.STALE and not include_stale:
            continue

        sky = resolved_aircraft_sky_position(observer, resolved)
        if sky is None or sky.elevation_deg < minimum_elevation_deg:
            continue

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
                position_state=resolved.state,
                position_age_seconds=max(
                    0.0,
                    (moment - resolved.source_observed_at).total_seconds(),
                ),
                source_id=snapshot.source_id,
                source_label=snapshot.source_label,
            )
        )

    return sorted(
        contacts,
        key=lambda contact: (-contact.elevation_deg, contact.range_km, contact.icao24),
    )


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aircraft live-view time must be timezone-aware")
    return value.astimezone(timezone.utc)
