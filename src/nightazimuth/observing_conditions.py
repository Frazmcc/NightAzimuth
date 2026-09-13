from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import Loader, wgs84
from timezonefinder import TimezoneFinder

from .config import ObserverConfig


_SKY_STATE_NAMES = {
    0: "Dark",
    1: "Astronomical twilight",
    2: "Nautical twilight",
    3: "Civil twilight",
    4: "Daylight",
}


@dataclass(frozen=True, slots=True)
class ObservingConditions:
    calculated_at_utc: datetime
    timezone_name: str
    sun_altitude_deg: float
    sky_state_code: int
    sunset_utc: datetime | None
    civil_twilight_end_utc: datetime | None
    nautical_twilight_end_utc: datetime | None
    astronomical_darkness_utc: datetime | None

    @property
    def sky_state_name(self) -> str:
        return sky_state_name(self.sky_state_code)

    @property
    def local_timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def local_time(self, moment: datetime | None) -> datetime | None:
        if moment is None:
            return None
        return moment.astimezone(self.local_timezone)


class ObservingConditionsEngine:
    """Calculate sunset and twilight state for the selected observer location."""

    def __init__(self, *, cache_directory: Path) -> None:
        self._loader = Loader(str(cache_directory / "skyfield"), verbose=False)
        self._timescale = self._loader.timescale()
        self._ephemeris = self._loader("de421.bsp")
        self._earth = self._ephemeris["earth"]
        self._sun = self._ephemeris["sun"]
        self._timezone_finder = TimezoneFinder(in_memory=True)

    def calculate(
        self,
        observer: ObserverConfig,
        *,
        at: datetime | None = None,
    ) -> ObservingConditions:
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Observing-condition time must be timezone-aware")
        moment = moment.astimezone(timezone.utc)

        timezone_name = self._timezone_finder.timezone_at(
            lng=observer.longitude,
            lat=observer.latitude,
        ) or "UTC"

        location = wgs84.latlon(
            observer.latitude,
            observer.longitude,
            elevation_m=observer.altitude_m,
        )
        t_now = self._timescale.from_datetime(moment)
        apparent_sun = (self._earth + location).at(t_now).observe(self._sun).apparent()
        sun_altitude, _, _ = apparent_sun.altaz()
        sun_altitude_deg = float(sun_altitude.degrees)

        twilight_function = almanac.dark_twilight_day(self._ephemeris, location)
        state_value = twilight_function(t_now)
        try:
            sky_state_code = int(state_value)
        except TypeError:
            sky_state_code = int(state_value[0])

        start = moment - timedelta(hours=24)
        end = moment + timedelta(hours=48)
        t0 = self._timescale.from_datetime(start)
        t1 = self._timescale.from_datetime(end)

        twilight_times, twilight_states = almanac.find_discrete(t0, t1, twilight_function)
        twilight_events = [
            (time.utc_datetime().replace(tzinfo=timezone.utc), int(state))
            for time, state in zip(twilight_times, twilight_states, strict=True)
        ]

        sunset_function = almanac.sunrise_sunset(self._ephemeris, location)
        sunset_times, sunset_states = almanac.find_discrete(t0, t1, sunset_function)
        sunset_events = [
            (time.utc_datetime().replace(tzinfo=timezone.utc), bool(state))
            for time, state in zip(sunset_times, sunset_states, strict=True)
        ]

        after_sunset = sky_state_code < 4
        after_civil_twilight = sky_state_code <= 2
        after_nautical_twilight = sky_state_code <= 1
        fully_dark = sky_state_code == 0

        return ObservingConditions(
            calculated_at_utc=moment,
            timezone_name=timezone_name,
            sun_altitude_deg=sun_altitude_deg,
            sky_state_code=sky_state_code,
            sunset_utc=_select_transition(
                sunset_events,
                moment,
                target=False,
                already_reached=after_sunset,
            ),
            civil_twilight_end_utc=_select_transition(
                twilight_events,
                moment,
                target=2,
                already_reached=after_civil_twilight,
            ),
            nautical_twilight_end_utc=_select_transition(
                twilight_events,
                moment,
                target=1,
                already_reached=after_nautical_twilight,
            ),
            astronomical_darkness_utc=_select_transition(
                twilight_events,
                moment,
                target=0,
                already_reached=fully_dark,
            ),
        )


def sky_state_name(code: int) -> str:
    return _SKY_STATE_NAMES.get(int(code), "Unknown")


def format_countdown(event_utc: datetime | None, now_utc: datetime, *, reached: bool) -> str:
    if event_utc is None:
        return "no transition"
    if reached:
        return "reached"

    remaining = max(0, int((event_utc - now_utc).total_seconds()))
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"in {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"in {minutes:02d}:{seconds:02d}"


def _select_transition(
    events: list[tuple[datetime, object]],
    moment: datetime,
    *,
    target: object,
    already_reached: bool,
) -> datetime | None:
    matching = [event_time for event_time, state in events if state == target]
    if already_reached:
        previous = [event_time for event_time in matching if event_time <= moment]
        return previous[-1] if previous else None
    future = [event_time for event_time in matching if event_time > moment]
    return future[0] if future else None
