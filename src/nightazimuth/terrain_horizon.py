from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
from typing import Protocol

from PIL import Image


EARTH_RADIUS_M = 6_371_000.0
TILE_SIZE = 256


class ElevationSource(Protocol):
    def elevation_m(self, latitude: float, longitude: float) -> float: ...


class MissingTerrainDataError(RuntimeError):
    """Raised when the installed offline terrain pack does not cover a requested point."""


@dataclass(frozen=True, slots=True)
class HorizonPoint:
    azimuth_deg: float
    elevation_deg: float


class OfflineTerrariumElevationSource:
    """Read Terrarium elevation tiles from a local-only terrain pack.

    The source performs no network access. Tile lookup is derived locally from the
    observer coordinates and only reads files beneath ``terrain_directory``.
    """

    def __init__(self, terrain_directory: Path, *, zoom: int = 10) -> None:
        self.terrain_directory = terrain_directory
        self.zoom = max(0, min(14, int(zoom)))
        self._images: dict[tuple[int, int], Image.Image] = {}

    def elevation_m(self, latitude: float, longitude: float) -> float:
        tile_x, tile_y, pixel_x, pixel_y = _tile_pixel(latitude, longitude, self.zoom)
        image = self._load_tile(tile_x, tile_y)
        red, green, blue = image.getpixel((pixel_x, pixel_y))[:3]
        return red * 256.0 + green + blue / 256.0 - 32768.0

    def _load_tile(self, tile_x: int, tile_y: int) -> Image.Image:
        key = (tile_x, tile_y)
        cached = self._images.get(key)
        if cached is not None:
            return cached

        path = self.terrain_directory / str(self.zoom) / str(tile_x) / f"{tile_y}.png"
        if not path.is_file():
            raise MissingTerrainDataError(
                "The installed offline terrain pack does not cover this observing location. "
                "No network request was made."
            )

        data = path.read_bytes()
        image = Image.open(BytesIO(data)).convert("RGB")
        self._images[key] = image
        return image


def calculate_horizon_profile(
    source: ElevationSource,
    *,
    observer_latitude: float,
    observer_longitude: float,
    observer_altitude_m: float,
    observer_height_m: float = 1.7,
    azimuth_step_deg: float = 1.0,
    max_distance_km: float = 80.0,
) -> tuple[HorizonPoint, ...]:
    """Calculate the highest terrain angle around the observer.

    The result is terrain-only. Nearby trees, buildings, fences and other local
    obstructions are intentionally outside the DEM model.
    """
    step = max(0.25, min(10.0, float(azimuth_step_deg)))
    max_distance_m = max(1_000.0, float(max_distance_km) * 1_000.0)
    observer_eye_m = float(observer_altitude_m) + float(observer_height_m)
    distances_m = _sample_distances(max_distance_m)

    points: list[HorizonPoint] = []
    azimuth = 0.0
    while azimuth < 360.0 - 1e-9:
        highest = 0.0
        for distance_m in distances_m:
            latitude, longitude = destination_point(
                observer_latitude,
                observer_longitude,
                azimuth,
                distance_m,
            )
            terrain_m = source.elevation_m(latitude, longitude)
            angle = apparent_elevation_deg(
                observer_eye_m,
                terrain_m,
                distance_m,
            )
            if angle > highest:
                highest = angle
        points.append(HorizonPoint(azimuth, max(0.0, highest)))
        azimuth += step

    return tuple(points)


def apparent_elevation_deg(
    observer_altitude_m: float,
    target_altitude_m: float,
    distance_m: float,
) -> float:
    """Return geometric apparent elevation, including Earth curvature."""
    distance = max(1.0, float(distance_m))
    curvature_drop = distance * distance / (2.0 * EARTH_RADIUS_M)
    relative_height = float(target_altitude_m) - float(observer_altitude_m) - curvature_drop
    return math.degrees(math.atan2(relative_height, distance))


def destination_point(
    latitude_deg: float,
    longitude_deg: float,
    bearing_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    """Return the spherical-Earth destination point for a bearing and distance."""
    latitude = math.radians(latitude_deg)
    longitude = math.radians(longitude_deg)
    bearing = math.radians(bearing_deg)
    angular_distance = float(distance_m) / EARTH_RADIUS_M

    target_latitude = math.asin(
        math.sin(latitude) * math.cos(angular_distance)
        + math.cos(latitude) * math.sin(angular_distance) * math.cos(bearing)
    )
    target_longitude = longitude + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(latitude),
        math.cos(angular_distance) - math.sin(latitude) * math.sin(target_latitude),
    )
    normalized_longitude = (math.degrees(target_longitude) + 540.0) % 360.0 - 180.0
    return math.degrees(target_latitude), normalized_longitude


def _sample_distances(max_distance_m: float) -> tuple[float, ...]:
    distances_km = (
        0.25,
        0.5,
        0.75,
        1.0,
        1.5,
        2.0,
        3.0,
        4.0,
        6.0,
        8.0,
        12.0,
        16.0,
        24.0,
        32.0,
        48.0,
        64.0,
        80.0,
        100.0,
    )
    result = [distance * 1_000.0 for distance in distances_km if distance * 1_000.0 <= max_distance_m]
    if not result or result[-1] < max_distance_m:
        result.append(max_distance_m)
    return tuple(result)


def _tile_pixel(
    latitude: float,
    longitude: float,
    zoom: int,
) -> tuple[int, int, int, int]:
    latitude = max(-85.05112878, min(85.05112878, float(latitude)))
    longitude = (float(longitude) + 180.0) % 360.0 - 180.0
    scale = 2**zoom

    x = (longitude + 180.0) / 360.0 * scale
    latitude_rad = math.radians(latitude)
    y = (1.0 - math.asinh(math.tan(latitude_rad)) / math.pi) / 2.0 * scale

    tile_x = int(math.floor(x)) % scale
    tile_y = max(0, min(scale - 1, int(math.floor(y))))
    pixel_x = max(0, min(TILE_SIZE - 1, int((x - math.floor(x)) * TILE_SIZE)))
    pixel_y = max(0, min(TILE_SIZE - 1, int((y - math.floor(y)) * TILE_SIZE)))
    return tile_x, tile_y, pixel_x, pixel_y
