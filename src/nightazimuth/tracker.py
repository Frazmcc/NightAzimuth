from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from skyfield.api import EarthSatellite, load, wgs84
from skyfield.positionlib import build_position

from .config import ObserverConfig


@dataclass(frozen=True, slots=True)
class SatellitePosition:
    name: str
    norad_id: str
    azimuth_deg: float
    elevation_deg: float
    range_km: float


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
        t = self._timescale.from_datetime(utc_moment)
        fields_list = list(elements)
        if not fields_list:
            return []

        # Skyfield can propagate an array of satellites in one SGP4 operation.  This
        # is substantially faster than building a topocentric position separately
        # for every object in CelesTrak ACTIVE on each web request.
        satellites = [EarthSatellite.from_omm(self._timescale, fields) for fields in fields_list]
        geocentric = satellites[0].at(t) if len(satellites) == 1 else None
        if geocentric is None:
            import numpy as np

            positions = [satellite.at(t) for satellite in satellites]
            geocentric = build_position(
                np.column_stack([position.position.au for position in positions]),
                np.column_stack([position.velocity.au_per_d for position in positions]),
                t=t,
                center=399,
            )

        observer_at = self._observer_position.at(t)
        topocentric = geocentric - observer_at
        altitudes, azimuths, distances = topocentric.altaz()
        altitude_values = np.atleast_1d(altitudes.degrees) if len(satellites) > 1 else [float(altitudes.degrees)]
        azimuth_values = np.atleast_1d(azimuths.degrees) if len(satellites) > 1 else [float(azimuths.degrees)]
        distance_values = np.atleast_1d(distances.km) if len(satellites) > 1 else [float(distances.km)]
        results: list[SatellitePosition] = []
        for fields, satellite, elevation_deg, azimuth_deg, range_km in zip(fields_list, satellites, altitude_values, azimuth_values, distance_values, strict=True):
            elevation_deg = float(elevation_deg)
            if elevation_deg < minimum_elevation_deg:
                continue
            results.append(SatellitePosition(name=str(fields.get("OBJECT_NAME") or satellite.name or "UNKNOWN"),norad_id=str(fields.get("NORAD_CAT_ID") or ""),azimuth_deg=float(azimuth_deg) % 360.0,elevation_deg=elevation_deg,range_km=float(range_km)))

        return sorted(results, key=lambda item: item.elevation_deg, reverse=True)
