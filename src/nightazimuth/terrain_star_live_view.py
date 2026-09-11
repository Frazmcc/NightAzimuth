from __future__ import annotations

from collections.abc import Iterable

from .live_view import signed_angular_difference
from .star_live_view import StarLiveSkyView
from .terrain_horizon import HorizonPoint


def terrain_profile_for_view(
    horizon: Iterable[HorizonPoint],
    *,
    facing_deg: float,
    horizontal_fov_deg: float,
    minimum_elevation_deg: float,
    maximum_elevation_deg: float,
) -> tuple[tuple[float, float], ...]:
    """Project a 360° terrain skyline into the current live-view window.

    Returned coordinates are fractions in the live-view plot where x=0..1 spans
    the horizontal field of view and y=0..1 spans the selected elevation range.
    Terrain below the current vertical window is clamped to the bottom edge and
    terrain above it is clamped to the top edge.
    """
    fov = max(5.0, min(180.0, float(horizontal_fov_deg)))
    minimum = max(0.0, min(89.0, float(minimum_elevation_deg)))
    maximum = max(minimum + 1.0, min(90.0, float(maximum_elevation_deg)))
    half_fov = fov / 2.0

    projected: list[tuple[float, float]] = []
    for point in horizon:
        offset = signed_angular_difference(point.azimuth_deg, facing_deg)
        if abs(offset) > half_fov:
            continue
        x_fraction = 0.5 + offset / fov
        elevation = max(minimum, min(maximum, point.elevation_deg))
        y_fraction = 1.0 - (elevation - minimum) / (maximum - minimum)
        projected.append((x_fraction, y_fraction))

    projected.sort(key=lambda item: item[0])
    return tuple(projected)


class TerrainStarLiveSkyView(StarLiveSkyView):
    """Live celestial view with a locally calculated terrain silhouette."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._terrain_horizon: tuple[HorizonPoint, ...] = ()
        super().__init__(*args, **kwargs)

    def set_terrain_horizon(self, horizon: tuple[HorizonPoint, ...] | None) -> None:
        self._terrain_horizon = horizon or ()
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        if not self._terrain_horizon:
            return

        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        profile = terrain_profile_for_view(
            self._terrain_horizon,
            facing_deg=self.facing_deg,
            horizontal_fov_deg=self.horizontal_fov_deg,
            minimum_elevation_deg=self.minimum_elevation_deg,
            maximum_elevation_deg=self.maximum_elevation_deg,
        )
        if not profile:
            return

        skyline = [
            (left + x_fraction * plot_width, top + y_fraction * plot_height)
            for x_fraction, y_fraction in profile
        ]
        first_y = skyline[0][1]
        last_y = skyline[-1][1]
        polygon = [
            (left, bottom),
            (left, first_y),
            *skyline,
            (right, last_y),
            (right, bottom),
        ]
        flattened = [coordinate for point in polygon for coordinate in point]
        skyline_flattened = [coordinate for point in skyline for coordinate in point]

        self.create_polygon(
            *flattened,
            fill="#182433",
            outline="",
            tags=("terrain-horizon",),
        )
        if len(skyline) >= 2:
            self.create_line(
                *skyline_flattened,
                fill="#8fa77a",
                width=2,
                tags=("terrain-horizon",),
            )

        # Terrain should hide celestial objects that are geometrically below the
        # local skyline, while satellites and their projected tracks stay on top.
        for tag in ("star-field", "constellation-line", "planet-field"):
            if self.find_withtag(tag):
                self.tag_raise("terrain-horizon", tag)
        if self.find_withtag("projected-track"):
            self.tag_raise("projected-track")
        for satellite in self._satellites:
            tag = f"live-sat:{satellite.norad_id}"
            if self.find_withtag(tag):
                self.tag_raise(tag)
