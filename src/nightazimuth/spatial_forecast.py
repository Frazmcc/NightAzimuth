from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .config import ObserverConfig
from .weather import MetNorwayWeatherProvider, WeatherPoint, WeatherSnapshot

GRID_SIZE = 3
RENDER_SIZE = 160


@dataclass(frozen=True, slots=True)
class SpatialForecastSnapshot:
    image: Image.Image
    valid_time_utc: datetime
    cloud_grid: tuple[tuple[float | None, ...], ...]
    rain_grid: tuple[tuple[float | None, ...], ...]
    source_name: str


class MetNorwaySpatialForecastProvider:
    """Build a small spatial forecast grid from free MET Norway point forecasts.

    This is deliberately a coarse forecast field for planning. It must not be
    presented as future satellite/radar imagery or exact cloud-edge placement.
    """

    def __init__(self, *, cache_directory: Path, timeout_seconds: float = 20.0) -> None:
        self._provider = MetNorwayWeatherProvider(
            cache_directory=cache_directory,
            cache_max_age_minutes=30,
            timeout_seconds=timeout_seconds,
        )

    def load_region(
        self,
        *,
        south: float,
        west: float,
        north: float,
        east: float,
        altitude_m: float,
        target_time_utc: datetime,
    ) -> SpatialForecastSnapshot:
        target = target_time_utc.astimezone(timezone.utc)
        latitudes = _linspace(north, south, GRID_SIZE)
        longitudes = _linspace(west, east, GRID_SIZE)
        observers = [
            ObserverConfig(latitude=lat, longitude=lon, altitude_m=altitude_m)
            for lat in latitudes
            for lon in longitudes
        ]
        with ThreadPoolExecutor(max_workers=4) as executor:
            snapshots = list(executor.map(self._provider.load, observers))

        cloud_rows: list[tuple[float | None, ...]] = []
        rain_rows: list[tuple[float | None, ...]] = []
        valid_times: list[datetime] = []
        for row in range(GRID_SIZE):
            cloud_values: list[float | None] = []
            rain_values: list[float | None] = []
            for column in range(GRID_SIZE):
                snapshot = snapshots[row * GRID_SIZE + column]
                point = nearest_forecast_point(snapshot, target)
                if point is None:
                    cloud_values.append(None)
                    rain_values.append(None)
                else:
                    cloud_values.append(_bounded_percent(point.cloud_total_percent))
                    rain_values.append(point.precipitation_next_hour_mm)
                    valid_times.append(point.time_utc)
            cloud_rows.append(tuple(cloud_values))
            rain_rows.append(tuple(rain_values))

        valid_time = min(valid_times, key=lambda value: abs((value - target).total_seconds())) if valid_times else target
        cloud_grid = tuple(cloud_rows)
        rain_grid = tuple(rain_rows)
        image = render_spatial_forecast(cloud_grid, rain_grid, width=RENDER_SIZE, height=RENDER_SIZE)
        return SpatialForecastSnapshot(
            image=image,
            valid_time_utc=valid_time,
            cloud_grid=cloud_grid,
            rain_grid=rain_grid,
            source_name="MET Norway Locationforecast 2.0 spatial sample",
        )


def nearest_forecast_point(snapshot: WeatherSnapshot, target_time_utc: datetime) -> WeatherPoint | None:
    if not snapshot.points:
        return None
    target = target_time_utc.astimezone(timezone.utc)
    return min(snapshot.points, key=lambda point: abs((point.time_utc - target).total_seconds()))


def render_spatial_forecast(
    cloud_grid: tuple[tuple[float | None, ...], ...],
    rain_grid: tuple[tuple[float | None, ...], ...],
    *,
    width: int,
    height: int,
) -> Image.Image:
    if width <= 0 or height <= 0:
        raise ValueError("Forecast render dimensions must be positive")
    if len(cloud_grid) < 2 or any(len(row) < 2 for row in cloud_grid):
        raise ValueError("Cloud forecast grid must be at least 2x2")

    rows = len(cloud_grid)
    columns = len(cloud_grid[0])
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = output.load()
    for y in range(height):
        gy = (y / max(1, height - 1)) * (rows - 1)
        y0 = min(rows - 2, int(gy))
        fy = gy - y0
        for x in range(width):
            gx = (x / max(1, width - 1)) * (columns - 1)
            x0 = min(columns - 2, int(gx))
            fx = gx - x0
            cloud = _bilinear_optional(cloud_grid, x0, y0, fx, fy)
            rain = _bilinear_optional(rain_grid, x0, y0, fx, fy)
            cloud_fraction = 0.0 if cloud is None else max(0.0, min(1.0, cloud / 100.0))
            rain_strength = 0.0 if rain is None else max(0.0, min(1.0, rain / 2.0))
            if cloud_fraction <= 0.01 and rain_strength <= 0.01:
                continue
            red = int(210 - 90 * rain_strength)
            green = int(220 - 70 * rain_strength)
            blue = int(230 + 25 * rain_strength)
            alpha = int(max(cloud_fraction * 145, rain_strength * 165))
            pixels[x, y] = (red, green, min(255, blue), alpha)
    return output


def _bilinear_optional(
    grid: tuple[tuple[float | None, ...], ...],
    x0: int,
    y0: int,
    fx: float,
    fy: float,
) -> float | None:
    values = (
        (grid[y0][x0], (1.0 - fx) * (1.0 - fy)),
        (grid[y0][x0 + 1], fx * (1.0 - fy)),
        (grid[y0 + 1][x0], (1.0 - fx) * fy),
        (grid[y0 + 1][x0 + 1], fx * fy),
    )
    weighted = [(float(value), weight) for value, weight in values if value is not None]
    if not weighted:
        return None
    total_weight = sum(weight for _, weight in weighted)
    if total_weight <= 0.0:
        return weighted[0][0]
    return sum(value * weight for value, weight in weighted) / total_weight


def _linspace(start: float, end: float, count: int) -> tuple[float, ...]:
    if count <= 1:
        return (start,)
    step = (end - start) / (count - 1)
    return tuple(start + index * step for index in range(count))


def _bounded_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, float(value)))
