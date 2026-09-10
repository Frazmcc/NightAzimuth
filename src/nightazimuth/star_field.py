from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from skyfield.api import Loader, Star, wgs84
from skyfield.data import hipparcos

from .config import ObserverConfig


MODERN_SKYCULTURE_URL = (
    "https://raw.githubusercontent.com/Stellarium/stellarium/"
    "2b10b1a3bb534eb4e7586751054bf67b36c22e53/"
    "skycultures/modern_st/index.json"
)


@dataclass(frozen=True, slots=True)
class StarPoint:
    hip_id: int
    azimuth_deg: float
    elevation_deg: float
    magnitude: float
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ConstellationLine:
    constellation: str
    start_azimuth_deg: float
    start_elevation_deg: float
    end_azimuth_deg: float
    end_elevation_deg: float


@dataclass(frozen=True, slots=True)
class StarFieldSnapshot:
    stars: tuple[StarPoint, ...]
    constellation_lines: tuple[ConstellationLine, ...]
    calculated_at: datetime


def parse_modern_skyculture(
    document: dict[str, Any],
) -> tuple[dict[int, str], tuple[tuple[str, int, int], ...]]:
    """Return Hipparcos proper names and constellation edges from Stellarium JSON."""
    names: dict[int, str] = {}
    for key, entries in document.get("common_names", {}).items():
        if not isinstance(key, str) or not key.startswith("HIP "):
            continue
        try:
            hip_id = int(key.split()[1])
        except (IndexError, ValueError):
            continue
        if not isinstance(entries, list) or not entries:
            continue
        first = entries[0]
        if not isinstance(first, dict):
            continue
        name = first.get("english") or first.get("native")
        if name:
            names[hip_id] = str(name)

    edges: list[tuple[str, int, int]] = []
    for constellation in document.get("constellations", []):
        if not isinstance(constellation, dict):
            continue
        identifier = str(constellation.get("id", ""))
        abbreviation = identifier.rsplit(" ", 1)[-1] if identifier else ""
        for polyline in constellation.get("lines", []):
            if not isinstance(polyline, list) or len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                try:
                    edges.append((abbreviation, int(start), int(end)))
                except (TypeError, ValueError):
                    continue

    return names, tuple(edges)


class StarFieldEngine:
    """Calculate a real topocentric star field for an observer."""

    def __init__(
        self,
        observer: ObserverConfig,
        cache_directory: str | Path,
        *,
        limiting_magnitude: float = 5.5,
    ) -> None:
        self.observer = observer
        self.cache_directory = Path(cache_directory)
        self.limiting_magnitude = limiting_magnitude
        self._loader = Loader(str(self.cache_directory), verbose=False, expire=False)

    def snapshot(self, *, at: datetime | None = None) -> StarFieldSnapshot:
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("Star-field time must be timezone-aware")
        moment = moment.astimezone(timezone.utc)

        # Hipparcos gives the real stellar coordinates and apparent magnitudes.
        # Skyfield applies proper motion when constructing Star objects from the
        # catalogue dataframe.
        with self._loader.open(hipparcos.URL) as handle:
            catalogue = hipparcos.load_dataframe(handle)
        catalogue = catalogue[catalogue["ra_degrees"].notnull()]

        with self._loader.open(
            MODERN_SKYCULTURE_URL,
            filename="stellarium-modern-st-index.json",
        ) as handle:
            skyculture = json.load(handle)
        proper_names, edges = parse_modern_skyculture(skyculture)

        bright = catalogue[catalogue["magnitude"] <= self.limiting_magnitude]
        edge_ids = {hip_id for _abbr, start, end in edges for hip_id in (start, end)}
        wanted_ids = set(int(value) for value in bright.index) | edge_ids
        selected_ids = catalogue.index.intersection(sorted(wanted_ids))
        selected = catalogue.loc[selected_ids]

        planets = self._loader("de421.bsp")
        earth = planets["earth"]
        topocentric_observer = earth + wgs84.latlon(
            self.observer.latitude,
            self.observer.longitude,
            elevation_m=self.observer.altitude_m,
        )
        timescale = self._loader.timescale()
        t = timescale.from_datetime(moment)
        apparent = topocentric_observer.at(t).observe(Star.from_dataframe(selected)).apparent()
        altitude, azimuth, _distance = apparent.altaz()

        position_map: dict[int, tuple[float, float]] = {}
        for hip_id, az_deg, alt_deg in zip(
            selected.index,
            azimuth.degrees,
            altitude.degrees,
        ):
            position_map[int(hip_id)] = (float(az_deg) % 360.0, float(alt_deg))

        bright_ids = set(int(value) for value in bright.index)
        stars: list[StarPoint] = []
        for hip_id in bright_ids:
            position = position_map.get(hip_id)
            if position is None or position[1] < 0.0:
                continue
            magnitude = float(catalogue.at[hip_id, "magnitude"])
            stars.append(
                StarPoint(
                    hip_id=hip_id,
                    azimuth_deg=position[0],
                    elevation_deg=position[1],
                    magnitude=magnitude,
                    name=proper_names.get(hip_id),
                )
            )

        lines: list[ConstellationLine] = []
        for abbreviation, start_id, end_id in edges:
            start = position_map.get(start_id)
            end = position_map.get(end_id)
            if start is None or end is None:
                continue
            if start[1] < 0.0 and end[1] < 0.0:
                continue
            lines.append(
                ConstellationLine(
                    constellation=abbreviation,
                    start_azimuth_deg=start[0],
                    start_elevation_deg=start[1],
                    end_azimuth_deg=end[0],
                    end_elevation_deg=end[1],
                )
            )

        stars.sort(key=lambda star: star.magnitude)
        return StarFieldSnapshot(tuple(stars), tuple(lines), moment)
