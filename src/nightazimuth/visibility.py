from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skyfield.api import EarthSatellite, Loader, wgs84

from .brightness import phase_angle_degrees
from .config import ObserverConfig


@dataclass(frozen=True, slots=True)
class VisibilityStatus:
    sun_altitude_deg: float
    satellite_sunlit: bool
    sky_dark: bool
    potentially_visible: bool
    phase_angle_deg: float


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

        # NightAzimuth.exe is built as a windowed application with no console.
        # Skyfield's default download progress output expects a writable stderr
        # stream, which PyInstaller intentionally removes in windowed mode.
        # Disable Loader verbosity so first-run ephemeris downloads are silent
        # and safe inside the GUI executable.
        self._loader = Loader(str(cache_directory / "skyfield"), verbose=False)
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

        satellite_at = satellite.at(t)
        satellite_sunlit = bool(satellite_at.is_sunlit(self._ephemeris))
        sky_dark = sun_altitude_deg <= self.darkness_threshold_deg

        # All three positions below are expressed in the same geocentric frame.
        # Subtracting the satellite position produces the two satellite-centred
        # vectors required for the Sun-satellite-observer phase angle.
        sun_geocentric_km = self._earth.at(t).observe(self._sun).position.km
        observer_geocentric_km = self._observer.at(t).position.km
        satellite_geocentric_km = satellite_at.position.km
        phase_angle_deg = phase_angle_degrees(
            sun_geocentric_km - satellite_geocentric_km,
            observer_geocentric_km - satellite_geocentric_km,
        )

        return VisibilityStatus(
            sun_altitude_deg=sun_altitude_deg,
            satellite_sunlit=satellite_sunlit,
            sky_dark=sky_dark,
            potentially_visible=satellite_sunlit and sky_dark,
            phase_angle_deg=phase_angle_deg,
        )
