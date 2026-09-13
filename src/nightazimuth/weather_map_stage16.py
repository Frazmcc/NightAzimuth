from __future__ import annotations

from dataclasses import dataclass
import math

from PIL import Image, ImageDraw

from .cloud_imagery import CloudImageSnapshot, EumetViewCloudProvider
from .cloud_projection import CloudRegion
from .config import ObserverConfig
from .weather_map import TILE_SIZE, WeatherMapRenderer, WeatherMapSnapshot, latlon_to_tile_fraction


@dataclass(frozen=True, slots=True)
class Stage16WeatherMapSnapshot:
    image: Image.Image
    radar_time_utc: object | None
    radar_enabled: bool
    cloud_enabled: bool
    cloud_region: CloudRegion | None
    cloud_from_cache: bool | None
    zoom: int


class Stage16WeatherMapRenderer(WeatherMapRenderer):
    """Stage 15 map plus optional EUMETView geostationary cloud imagery."""

    def __init__(self, *, cache_directory, timeout_seconds: float = 20.0) -> None:
        super().__init__(cache_directory=cache_directory, timeout_seconds=timeout_seconds)
        self._cloud_provider = EumetViewCloudProvider(
            cache_directory=cache_directory,
            timeout_seconds=max(20.0, timeout_seconds),
        )

    def render_stage16(
        self,
        observer: ObserverConfig,
        *,
        show_radar: bool,
        show_cloud: bool,
        zoom: int = 7,
        radius_tiles: int = 1,
    ) -> Stage16WeatherMapSnapshot:
        base: WeatherMapSnapshot = super().render(
            observer,
            show_radar=show_radar,
            zoom=zoom,
            radius_tiles=radius_tiles,
        )
        if not show_cloud:
            return Stage16WeatherMapSnapshot(
                image=base.image,
                radar_time_utc=base.radar_time_utc,
                radar_enabled=base.radar_enabled,
                cloud_enabled=False,
                cloud_region=None,
                cloud_from_cache=None,
                zoom=base.zoom,
            )

        min_lat, min_lon, max_lat, max_lon = map_bbox_for_view(
            observer.latitude,
            observer.longitude,
            zoom=zoom,
            radius_tiles=radius_tiles,
        )
        cloud: CloudImageSnapshot = self._cloud_provider.load_region(
            min_latitude=min_lat,
            min_longitude=min_lon,
            max_latitude=max_lat,
            max_longitude=max_lon,
            width=base.image.width,
            height=base.image.height,
        )
        cloud_image = cloud.image.convert("RGBA")
        cloud_image.putalpha(110)
        merged = Image.alpha_composite(base.image.convert("RGBA"), cloud_image).convert("RGB")
        _redraw_observer_marker(merged, observer, zoom=zoom, radius_tiles=radius_tiles)
        _add_cloud_attribution(merged, cloud.from_cache)
        region = CloudRegion(
            image=cloud.image,
            min_latitude=min_lat,
            min_longitude=min_lon,
            max_latitude=max_lat,
            max_longitude=max_lon,
            source_name=cloud.source_name,
            from_cache=cloud.from_cache,
        )
        return Stage16WeatherMapSnapshot(
            image=merged,
            radar_time_utc=base.radar_time_utc,
            radar_enabled=base.radar_enabled,
            cloud_enabled=True,
            cloud_region=region,
            cloud_from_cache=cloud.from_cache,
            zoom=base.zoom,
        )


def map_bbox_for_view(
    latitude: float,
    longitude: float,
    *,
    zoom: int,
    radius_tiles: int,
) -> tuple[float, float, float, float]:
    centre_x, centre_y = latlon_to_tile_fraction(latitude, longitude, zoom)
    centre_tile_x = math.floor(centre_x)
    centre_tile_y = math.floor(centre_y)
    start_x = centre_tile_x - radius_tiles
    start_y = centre_tile_y - radius_tiles
    tiles_across = radius_tiles * 2 + 1
    north, west = tile_fraction_to_latlon(start_x, start_y, zoom)
    south, east = tile_fraction_to_latlon(start_x + tiles_across, start_y + tiles_across, zoom)
    return south, west, north, east


def tile_fraction_to_latlon(x: float, y: float, zoom: int) -> tuple[float, float]:
    scale = float(1 << zoom)
    longitude = x / scale * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / scale
    latitude = math.degrees(math.atan(math.sinh(n)))
    return latitude, longitude


def _redraw_observer_marker(
    image: Image.Image,
    observer: ObserverConfig,
    *,
    zoom: int,
    radius_tiles: int,
) -> None:
    centre_x, centre_y = latlon_to_tile_fraction(observer.latitude, observer.longitude, zoom)
    start_x = math.floor(centre_x) - radius_tiles
    start_y = math.floor(centre_y) - radius_tiles
    marker_x = (centre_x - start_x) * TILE_SIZE
    marker_y = (centre_y - start_y) * TILE_SIZE
    draw = ImageDraw.Draw(image)
    r = 8
    draw.ellipse((marker_x - r, marker_y - r, marker_x + r, marker_y + r), fill="white", outline="black", width=2)
    draw.line((marker_x - 12, marker_y, marker_x + 12, marker_y), fill="black", width=2)
    draw.line((marker_x, marker_y - 12, marker_x, marker_y + 12), fill="black", width=2)


def _add_cloud_attribution(image: Image.Image, from_cache: bool) -> None:
    draw = ImageDraw.Draw(image)
    label = "Cloud imagery: EUMETSAT EUMETView / NASA" + (" (cache)" if from_cache else "")
    box = draw.textbbox((0, 0), label)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = 8
    y = 8
    draw.rectangle((x - 4, y - 2, x + width + 4, y + height + 2), fill="white")
    draw.text((x, y), label, fill="black")
