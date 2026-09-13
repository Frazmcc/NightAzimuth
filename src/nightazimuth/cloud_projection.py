from __future__ import annotations

from dataclasses import dataclass
import math

from PIL import Image, ImageFilter

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True, slots=True)
class CloudRegion:
    image: Image.Image
    min_latitude: float
    min_longitude: float
    max_latitude: float
    max_longitude: float
    source_name: str
    from_cache: bool = False


def destination_latlon(
    latitude: float,
    longitude: float,
    azimuth_deg: float,
    distance_km: float,
) -> tuple[float, float]:
    """Move from a WGS84-like point along a great-circle approximation."""
    angular = max(0.0, distance_km) / EARTH_RADIUS_KM
    bearing = math.radians(azimuth_deg % 360.0)
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular)
        + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), ((math.degrees(lon2) + 180.0) % 360.0) - 180.0


def line_of_sight_cloud_distance_km(
    elevation_deg: float,
    *,
    assumed_cloud_altitude_km: float = 3.0,
    maximum_distance_km: float = 100.0,
) -> float:
    """Estimate where a sight line intersects an assumed horizontal cloud layer."""
    elevation = max(2.0, min(89.9, float(elevation_deg)))
    distance = assumed_cloud_altitude_km / math.tan(math.radians(elevation))
    return min(maximum_distance_km, max(0.0, distance))


def _sample_bilinear(source: Image.Image, x: float, y: float) -> tuple[int, int, int]:
    """Bilinearly sample an RGB image to avoid blocky nearest-neighbour cloud edges."""
    width, height = source.size
    x = max(0.0, min(width - 1.0, x))
    y = max(0.0, min(height - 1.0, y))
    x0 = int(math.floor(x))
    y0 = int(math.floor(y))
    x1 = min(width - 1, x0 + 1)
    y1 = min(height - 1, y0 + 1)
    fx = x - x0
    fy = y - y0
    pixels = source.load()
    c00 = pixels[x0, y0]
    c10 = pixels[x1, y0]
    c01 = pixels[x0, y1]
    c11 = pixels[x1, y1]
    values: list[int] = []
    for channel in range(3):
        top = c00[channel] * (1.0 - fx) + c10[channel] * fx
        bottom = c01[channel] * (1.0 - fx) + c11[channel] * fx
        values.append(int(round(top * (1.0 - fy) + bottom * fy)))
    return values[0], values[1], values[2]


def project_cloud_region(
    region: CloudRegion,
    *,
    observer_latitude: float,
    observer_longitude: float,
    facing_deg: float,
    horizontal_fov_deg: float,
    minimum_elevation_deg: float,
    maximum_elevation_deg: float,
    width: int = 180,
    height: int = 100,
    assumed_cloud_altitude_km: float = 3.0,
) -> Image.Image:
    """Create an indicative sky texture from geostationary satellite imagery.

    The result is deliberately visual rather than a quantified cloud mask. A
    single representative cloud altitude is used, so exact cloud/elevation
    alignment must be presented as an estimate.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Projection dimensions must be positive")
    if maximum_elevation_deg <= minimum_elevation_deg:
        raise ValueError("Elevation range must be positive")

    source = region.image.convert("RGB")
    src_width, src_height = source.size
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = output.load()

    lon_span = region.max_longitude - region.min_longitude
    lat_span = region.max_latitude - region.min_latitude
    if lon_span <= 0.0 or lat_span <= 0.0:
        return output

    for y in range(height):
        y_fraction = (y + 0.5) / height
        elevation = maximum_elevation_deg - y_fraction * (
            maximum_elevation_deg - minimum_elevation_deg
        )
        distance = line_of_sight_cloud_distance_km(
            elevation,
            assumed_cloud_altitude_km=assumed_cloud_altitude_km,
        )
        for x in range(width):
            x_fraction = (x + 0.5) / width
            azimuth = (
                facing_deg + (x_fraction - 0.5) * horizontal_fov_deg
            ) % 360.0
            latitude, longitude = destination_latlon(
                observer_latitude,
                observer_longitude,
                azimuth,
                distance,
            )
            if not (
                region.min_latitude <= latitude <= region.max_latitude
                and region.min_longitude <= longitude <= region.max_longitude
            ):
                continue
            u = (longitude - region.min_longitude) / lon_span
            v = (region.max_latitude - latitude) / lat_span
            sx = u * max(0, src_width - 1)
            sy = v * max(0, src_height - 1)
            red, green, blue = _sample_bilinear(source, sx, sy)

            # GeoColour uses bright/whitish or bluish tones for cloud. Keep the
            # overlay deliberately subdued and label it as indicative in UI.
            brightness = (red + green + blue) / 3.0
            blue_bias = max(0.0, blue - (red + green) / 2.0)
            strength = max(0.0, min(1.0, (brightness - 75.0) / 150.0 + blue_bias / 255.0))
            # Ease the mask so weak cloud does not form hard-edged slabs.
            strength = strength * strength * (3.0 - 2.0 * strength)
            alpha = int(105 * strength)
            if alpha > 5:
                pixels[x, y] = (190, 215, 235, alpha)

    # Satellite pixels and the assumed-height projection can otherwise leave
    # rectangular/blocky boundaries. Blur only the final visual texture; this
    # is an indicative overlay, not a scientific cloud mask.
    if width >= 40 and height >= 30:
        output = output.filter(ImageFilter.GaussianBlur(radius=1.25))
    return output
