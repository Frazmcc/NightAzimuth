from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from skyfield.api import EarthSatellite, load, wgs84

from .config import ObserverConfig


@dataclass(frozen=True, slots=True)
class SatellitePass:
    name: str
    norad_id: str
    rise_time: datetime
    culmination_time: datetime
    set_time: datetime
    max_elevation_deg: float


class PassPredictor:
    def __init__(self, observer: ObserverConfig) -> None:
        self.observer = observer
        self._timescale = load.timescale()
        self._observer = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )

    def predict(
        self,
        elements: Iterable[dict[str, Any]],
        *,
        start: datetime | None = None,
        hours: float = 24.0,
        minimum_elevation_deg: float = 10.0,
    ) -> list[SatellitePass]:
        if hours <= 0:
            return []

        start_time = start or datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            raise ValueError("Pass prediction start time must be timezone-aware")

        start_utc = start_time.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(hours=hours)
        t0 = self._timescale.from_datetime(start_utc)
        t1 = self._timescale.from_datetime(end_utc)

        predicted: list[SatellitePass] = []

        for fields in elements:
            satellite = EarthSatellite.from_omm(self._timescale, fields)
            times, events = satellite.find_events(
                self._observer,
                t0,
                t1,
                altitude_degrees=minimum_elevation_deg,
            )

            rise_time: datetime | None = None
            culmination_time: datetime | None = None
            culmination_elevation: float | None = None

            for event_time, event in zip(times, events, strict=True):
                event_dt = event_time.utc_datetime().replace(tzinfo=timezone.utc)

                if event == 0:
                    rise_time = event_dt
                    culmination_time = None
                    culmination_elevation = None
                elif event == 1 and rise_time is not None:
                    culmination_time = event_dt
                    altitude, _, _ = (satellite - self._observer).at(event_time).altaz()
                    culmination_elevation = float(altitude.degrees)
                elif event == 2 and rise_time is not None and culmination_time is not None:
                    name = str(fields.get("OBJECT_NAME") or satellite.name or "UNKNOWN")
                    norad_id = str(fields.get("NORAD_CAT_ID") or "")
                    predicted.append(
                        SatellitePass(
                            name=name,
                            norad_id=norad_id,
                            rise_time=rise_time,
                            culmination_time=culmination_time,
                            set_time=event_dt,
                            max_elevation_deg=culmination_elevation or minimum_elevation_deg,
                        )
                    )
                    rise_time = None
                    culmination_time = None
                    culmination_elevation = None

        return sorted(predicted, key=lambda item: item.rise_time)
