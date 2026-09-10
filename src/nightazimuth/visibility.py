from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skyfield.api import EarthSatellite, Loader, wgs84

from .config import ObserverConfig


@dataclass(frozen=True, slots=True)
class VisibilityStatus:
    sun_altitude_deg: float
    satellite_sunlit: bool
    sky_dark: bool
    potentially_visible: bool


class VisibilityEngine:
    """Evaluate basic astronomical visibility for satellites.

    This deliberately does not claim naked-eye visibility. It only determines
    whether the geometry is favourable: the satellite is sunlit while the
    observer's sky is sufficiently dark.
    """

    def __init__(
        self,
        observer: ObserverConfig,
        *,
        cache_directory: Path,
        darkness_threshold_deg: float = -6.0,
    ) -> None:
        self.observer = observer
        self.darkness_threshold_deg = darkness_threshold_deg
        self._loader = Loader(str(cache_directory / "skyfield"))
        self._timescale = self._loader.timescale()
        self._ephemeris = self._loader("de421.bsp")
        self._earth = self._ephemeris["earth"]
        self._sun = self._ephemeris["sun"]
        self._observer = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )

    def evaluate(
        self,
        fields: dict[str, Any],
        *,
        at: datetime | None = None,
    ) -> VisibilityStatus:
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Visibility time must be timezone-aware")

        t = self._timescale.from_datetime(moment.astimezone(timezone.utc))
        satellite = EarthSatellite.from_omm(self._timescale, fields)

        observer_at_earth = self._earth + self._observer
        apparent_sun = observer_at_earth.at(t).observe(self._sun).apparent()
        sun_altitude, _, _ = apparent_sun.altaz()
        sun_altitude_deg = float(sun_altitude.degrees)

        satellite_sunlit = bool(satellite.at(t).is_sunlit(self._ephemeris))
        sky_dark = sun_altitude_deg <= self.darkness_threshold_deg

        return VisibilityStatus(
            sun_altitude_deg=sun_altitude_deg,
            satellite_sunlit=satellite_sunlit,
            sky_dark=sky_dark,
            potentially_visible=satellite_sunlit and sky_dark,
        )
