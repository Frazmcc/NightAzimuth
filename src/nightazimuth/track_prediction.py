from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from skyfield.api import EarthSatellite, load, wgs84

from .config import ObserverConfig


@dataclass(frozen=True, slots=True)
class TrackPoint:
    """One predicted topocentric point in a short future satellite track."""

    seconds_from_now: int
    azimuth_deg: float
    elevation_deg: float


class TrackPredictor:
    """Generate short-horizon topocentric tracks for the Live view.

    This deliberately predicts only a few minutes ahead.  The purpose is to
    help an observer understand where to look next, not to replace the longer
    rise/peak/set pass predictor.
    """

    def __init__(self, observer: ObserverConfig) -> None:
        self.observer = observer
        self._timescale = load.timescale()
        self._observer_position = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )

    def predict(
        self,
        elements: Iterable[dict[str, Any]],
        *,
        duration_seconds: int = 180,
        step_seconds: int = 30,
        at: datetime | None = None,
    ) -> dict[str, tuple[TrackPoint, ...]]:
        if duration_seconds <= 0:
            raise ValueError("Track duration must be greater than zero")
        if step_seconds <= 0:
            raise ValueError("Track step must be greater than zero")

        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Tracking time must be timezone-aware")
        moment = moment.astimezone(timezone.utc)

        offsets = list(range(0, duration_seconds + 1, step_seconds))
        if offsets[-1] != duration_seconds:
            offsets.append(duration_seconds)

        datetimes = [moment + timedelta(seconds=offset) for offset in offsets]
        times = self._timescale.from_datetimes(datetimes)
        tracks: dict[str, tuple[TrackPoint, ...]] = {}

        for fields in elements:
            norad_id = str(fields.get("NORAD_CAT_ID") or "")
            if not norad_id:
                continue

            satellite = EarthSatellite.from_omm(self._timescale, fields)
            topocentric = (satellite - self._observer_position).at(times)
            altitude, azimuth, _distance = topocentric.altaz()

            points = tuple(
                TrackPoint(
                    seconds_from_now=offset,
                    azimuth_deg=float(azimuth.degrees[index]) % 360.0,
                    elevation_deg=float(altitude.degrees[index]),
                )
                for index, offset in enumerate(offsets)
            )

            # Keep tracks that are currently above the horizon or enter the
            # above-horizon sky during this short prediction window.
            if any(point.elevation_deg >= 0.0 for point in points):
                tracks[norad_id] = points

        return tracks
