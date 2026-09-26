from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from skyfield.api import EarthSatellite, load, wgs84

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
        results: list[SatellitePosition] = []

        for fields in elements:
            satellite = EarthSatellite.from_omm(self._timescale, fields)
            difference = satellite - self._observer_position
            topocentric = difference.at(t)
            altitude, azimuth, distance = topocentric.altaz()

            elevation_deg = float(altitude.degrees)
            if elevation_deg < minimum_elevation_deg:
                continue

            name = str(fields.get("OBJECT_NAME") or satellite.name or "UNKNOWN")
            norad_id = str(fields.get("NORAD_CAT_ID") or "")
            results.append(
                SatellitePosition(
                    name=name,
                    norad_id=norad_id,
                    azimuth_deg=float(azimuth.degrees) % 360.0,
                    elevation_deg=elevation_deg,
                    range_km=float(distance.km),
                )
            )

        return sorted(results, key=lambda item: item.elevation_deg, reverse=True)
