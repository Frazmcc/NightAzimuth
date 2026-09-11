from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
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

# A compact zero-cost deep-sky reference set for the Live finder. Coordinates
# are J2000 right ascension / declination and are transformed topocentrically
# with Skyfield for the observer and current time.
GALAXY_CATALOGUE: tuple[tuple[str, float, float], ...] = (
    ("Andromeda Galaxy (M31)", 0.7123056, 41.26917),
    ("Triangulum Galaxy (M33)", 1.5641389, 30.66028),
    ("Bode's Galaxy (M81)", 9.9258889, 69.06528),
    ("Cigar Galaxy (M82)", 9.9311667, 69.67972),
    ("Whirlpool Galaxy (M51)", 13.4979722, 47.19528),
    ("Pinwheel Galaxy (M101)", 14.0535000, 54.34917),
    ("Sombrero Galaxy (M104)", 12.6665000, -11.62306),
)


@dataclass(frozen=True, slots=True)
class StarPoint:
    hip_id: int
    azimuth_deg: float
    elevation_deg: float
    magnitude: float
    name: str | None = None


@dataclass(frozen=True, slots=True)
class PlanetPoint:
    name: str
    azimuth_deg: float
    elevation_deg: float


@dataclass(frozen=True, slots=True)
class DeepSkyPoint:
    name: str
    azimuth_deg: float
    elevation_deg: float
    object_type: str = "galaxy"


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
    planets: tuple[PlanetPoint, ...]
    constellation_lines: tuple[ConstellationLine, ...]
    calculated_at: datetime
    galaxies: tuple[DeepSkyPoint, ...] = ()


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
            for start, end in pairwise(polyline):
                try:
                    edges.append((abbreviation, int(start), int(end)))
                except (TypeError, ValueError):
                    continue

    return names, tuple(edges)


class StarFieldEngine:
    """Calculate real topocentric stars, planets and galaxy references for an observer."""

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
        moment = at or datetime.now(UTC)
        if moment.tzinfo is None:
            raise ValueError("Star-field time must be timezone-aware")
        moment = moment.astimezone(UTC)

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
        wanted_ids = {int(value) for value in bright.index} | edge_ids
        selected_ids = catalogue.index.intersection(sorted(wanted_ids))
        selected = catalogue.loc[selected_ids]

        ephemeris = self._loader("de421.bsp")
        earth = ephemeris["earth"]
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
            strict=True,
        ):
            position_map[int(hip_id)] = (float(az_deg) % 360.0, float(alt_deg))

        bright_ids = {int(value) for value in bright.index}
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

        planet_targets = (
            ("Mercury", "mercury"),
            ("Venus", "venus"),
            ("Mars", "mars"),
            ("Jupiter", "jupiter barycenter"),
            ("Saturn", "saturn barycenter"),
            ("Uranus", "uranus barycenter"),
            ("Neptune", "neptune barycenter"),
        )
        planet_points: list[PlanetPoint] = []
        for display_name, target_name in planet_targets:
            apparent_planet = topocentric_observer.at(t).observe(ephemeris[target_name]).apparent()
            planet_altitude, planet_azimuth, _planet_distance = apparent_planet.altaz()
            elevation = float(planet_altitude.degrees)
            if elevation < 0.0:
                continue
            planet_points.append(
                PlanetPoint(
                    name=display_name,
                    azimuth_deg=float(planet_azimuth.degrees) % 360.0,
                    elevation_deg=elevation,
                )
            )

        galaxy_points: list[DeepSkyPoint] = []
        for display_name, ra_hours, dec_degrees in GALAXY_CATALOGUE:
            apparent_galaxy = topocentric_observer.at(t).observe(
                Star(ra_hours=ra_hours, dec_degrees=dec_degrees)
            ).apparent()
            galaxy_altitude, galaxy_azimuth, _galaxy_distance = apparent_galaxy.altaz()
            elevation = float(galaxy_altitude.degrees)
            if elevation < 0.0:
                continue
            galaxy_points.append(
                DeepSkyPoint(
                    name=display_name,
                    azimuth_deg=float(galaxy_azimuth.degrees) % 360.0,
                    elevation_deg=elevation,
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
        return StarFieldSnapshot(
            tuple(stars),
            tuple(planet_points),
            tuple(lines),
            moment,
            tuple(galaxy_points),
        )