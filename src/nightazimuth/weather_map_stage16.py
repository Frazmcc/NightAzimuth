from __future__ import annotations

from dataclasses import dataclass
import math

from PIL import Image, ImageDraw

from .cloud_imagery import CloudImageSnapshot, EumetViewCloudProvider
from .cloud_projection import CloudRegion, destination_latlon
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
        facing_deg: float | None = None,
        horizontal_fov_deg: float | None = None,
    ) -> Stage16WeatherMapSnapshot:
        base: WeatherMapSnapshot = super().render(
            observer,
            show_radar=show_radar,
            zoom=zoom,
            radius_tiles=radius_tiles,
        )
        image = base.image
        region: CloudRegion | None = None
        cloud_from_cache: bool | None = None

        if show_cloud:
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
            image = Image.alpha_composite(base.image.convert("RGBA"), cloud_image).convert("RGB")
            cloud_from_cache = cloud.from_cache
            region = CloudRegion(
                image=cloud.image,
                min_latitude=min_lat,
                min_longitude=min_lon,
                max_latitude=max_lat,
                max_longitude=max_lon,
                source_name=cloud.source_name,
                from_cache=cloud.from_cache,
            )
            _add_cloud_attribution(image, cloud.from_cache)

        if facing_deg is not None and horizontal_fov_deg is not None:
            _draw_view_wedge(
                image,
                observer,
                zoom=zoom,
                radius_tiles=radius_tiles,
                facing_deg=facing_deg,
                horizontal_fov_deg=horizontal_fov_deg,
            )
        _redraw_observer_marker(image, observer, zoom=zoom, radius_tiles=radius_tiles)

        return Stage16WeatherMapSnapshot(
            image=image,
            radar_time_utc=base.radar_time_utc,
            radar_enabled=base.radar_enabled,
            cloud_enabled=show_cloud,
            cloud_region=region,
            cloud_from_cache=cloud_from_cache,
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


def _map_pixel_for_latlon(
    latitude: float,
    longitude: float,
    *,
    centre_x: float,
    centre_y: float,
    zoom: int,
    radius_tiles: int,
) -> tuple[float, float]:
    x, y = latlon_to_tile_fraction(latitude, longitude, zoom)
    start_x = math.floor(centre_x) - radius_tiles
    start_y = math.floor(centre_y) - radius_tiles
    return (x - start_x) * TILE_SIZE, (y - start_y) * TILE_SIZE


def _draw_view_wedge(
    image: Image.Image,
    observer: ObserverConfig,
    *,
    zoom: int,
    radius_tiles: int,
    facing_deg: float,
    horizontal_fov_deg: float,
) -> None:
    centre_x, centre_y = latlon_to_tile_fraction(observer.latitude, observer.longitude, zoom)
    origin = _map_pixel_for_latlon(
        observer.latitude,
        observer.longitude,
        centre_x=centre_x,
        centre_y=centre_y,
        zoom=zoom,
        radius_tiles=radius_tiles,
    )
    half = max(2.5, min(90.0, horizontal_fov_deg / 2.0))
    distance_km = 120.0
    left_lat, left_lon = destination_latlon(
        observer.latitude,
        observer.longitude,
        facing_deg - half,
        distance_km,
    )
    right_lat, right_lon = destination_latlon(
        observer.latitude,
        observer.longitude,
        facing_deg + half,
        distance_km,
    )
    centre_lat, centre_lon = destination_latlon(
        observer.latitude,
        observer.longitude,
        facing_deg,
        distance_km,
    )
    left = _map_pixel_for_latlon(
        left_lat,
        left_lon,
        centre_x=centre_x,
        centre_y=centre_y,
        zoom=zoom,
        radius_tiles=radius_tiles,
    )
    right = _map_pixel_for_latlon(
        right_lat,
        right_lon,
        centre_x=centre_x,
        centre_y=centre_y,
        zoom=zoom,
        radius_tiles=radius_tiles,
    )
    centre = _map_pixel_for_latlon(
        centre_lat,
        centre_lon,
        centre_x=centre_x,
        centre_y=centre_y,
        zoom=zoom,
        radius_tiles=radius_tiles,
    )
    draw = ImageDraw.Draw(image, "RGBA")
    draw.polygon((origin, left, right), fill=(34, 197, 94, 30), outline=(34, 197, 94, 180))
    draw.line((origin, centre), fill=(34, 197, 94, 220), width=3)
    draw.text((centre[0] + 4, centre[1] + 2), "LIVE VIEW", fill=(20, 90, 50, 255))


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
