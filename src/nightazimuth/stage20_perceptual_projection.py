from __future__ import annotations

from dataclasses import dataclass
import math

from .live_view import LiveProjection, signed_angular_difference


@dataclass(frozen=True, slots=True)
class PerceptualProjectionMetrics:
    """Useful perceptual metadata for a point in the Stage 20 live view."""

    projection: LiveProjection
    eccentricity: float


def project_perceptual_live_view(
    azimuth_deg: float,
    elevation_deg: float,
    facing_deg: float,
    horizontal_fov_deg: float,
    *,
    minimum_elevation_deg: float = 0.0,
    maximum_elevation_deg: float = 60.0,
) -> LiveProjection:
    """Project the sky using a stereographic observer-centred view.

    The legacy Live view maps azimuth/elevation linearly onto a rectangle. That
    is useful for plotting but it stretches wide fields unnaturally. Stage 20
    instead treats the sky as a sphere around the observer and projects that
    sphere stereographically around the centre of the current look direction.

    This keeps the centre geometrically stable, compresses the peripheral field
    in a human-like way and allows horizontal/elevation structures to curve
    naturally at wide field of view. It is a perceptual display projection, not
    a claim that celestial objects have binocular depth at astronomical range.
    """

    fov = max(5.0, min(175.0, float(horizontal_fov_deg)))
    minimum = max(0.0, min(89.0, float(minimum_elevation_deg)))
    maximum = max(minimum + 1.0, min(90.0, float(maximum_elevation_deg)))
    half_fov = fov / 2.0
    offset = signed_angular_difference(float(azimuth_deg), float(facing_deg))
    elevation = float(elevation_deg)
    visible = abs(offset) <= half_fov and minimum <= elevation <= maximum

    centre_elevation = (minimum + maximum) / 2.0
    raw_x, raw_y = _stereographic_coordinates(offset, elevation, centre_elevation)

    edge_x, _ = _stereographic_coordinates(half_fov, centre_elevation, centre_elevation)
    _, top_y = _stereographic_coordinates(0.0, maximum, centre_elevation)
    _, bottom_y = _stereographic_coordinates(0.0, minimum, centre_elevation)

    x_scale = max(abs(edge_x), 1.0e-9)
    vertical_span = max(top_y - bottom_y, 1.0e-9)
    x_fraction = 0.5 + 0.5 * raw_x / x_scale
    y_fraction = 1.0 - (raw_y - bottom_y) / vertical_span

    # Keep points numerically near the edge stable while preserving the real
    # angular visibility decision above.
    x_fraction = max(-0.15, min(1.15, x_fraction))
    y_fraction = max(-0.15, min(1.15, y_fraction))
    return LiveProjection(visible, x_fraction, y_fraction)


def project_perceptual_with_metrics(
    azimuth_deg: float,
    elevation_deg: float,
    facing_deg: float,
    horizontal_fov_deg: float,
    *,
    minimum_elevation_deg: float = 0.0,
    maximum_elevation_deg: float = 60.0,
) -> PerceptualProjectionMetrics:
    projection = project_perceptual_live_view(
        azimuth_deg,
        elevation_deg,
        facing_deg,
        horizontal_fov_deg,
        minimum_elevation_deg=minimum_elevation_deg,
        maximum_elevation_deg=maximum_elevation_deg,
    )
    dx = projection.x_fraction - 0.5
    dy = projection.y_fraction - 0.5
    eccentricity = min(1.0, math.hypot(dx / 0.5, dy / 0.5))
    return PerceptualProjectionMetrics(projection=projection, eccentricity=eccentricity)


def _stereographic_coordinates(
    azimuth_offset_deg: float,
    elevation_deg: float,
    centre_elevation_deg: float,
) -> tuple[float, float]:
    offset = math.radians(float(azimuth_offset_deg))
    elevation = math.radians(float(elevation_deg))
    centre = math.radians(float(centre_elevation_deg))

    # Local observer vector: x=right, y=forward, z=up.
    side = math.cos(elevation) * math.sin(offset)
    forward_horizontal = math.cos(elevation) * math.cos(offset)
    up = math.sin(elevation)

    # Rotate into a camera centred on the current look elevation.
    camera_x = side
    camera_y = -forward_horizontal * math.sin(centre) + up * math.cos(centre)
    camera_z = forward_horizontal * math.cos(centre) + up * math.sin(centre)

    denominator = max(1.0e-9, 1.0 + camera_z)
    return 2.0 * camera_x / denominator, 2.0 * camera_y / denominator
