from __future__ import annotations

from .live_view import LiveSkyView, project_live_view
from .star_field import StarFieldSnapshot, StarPoint


def star_marker_radius(magnitude: float) -> float:
    """Return a readable marker size while preserving relative brightness."""
    if magnitude <= 0.0:
        return 3.5
    if magnitude <= 1.0:
        return 3.0
    if magnitude <= 2.0:
        return 2.5
    if magnitude <= 3.0:
        return 2.0
    if magnitude <= 4.0:
        return 1.5
    return 1.0


class StarLiveSkyView(LiveSkyView):
    """LiveSkyView with a real stellar reference layer underneath satellites."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._star_snapshot: StarFieldSnapshot | None = None
        self._star_snapshot_profile: str | None = None
        self._show_stars = True
        self._show_constellations = False
        super().__init__(*args, **kwargs)

    def _current_profile_name(self) -> str | None:
        """Return the currently selected observer profile from the owning app."""
        selected = getattr(self.winfo_toplevel(), "selected_name", None)
        return str(selected) if selected else None

    def set_star_field(self, snapshot: StarFieldSnapshot | None) -> None:
        self._star_snapshot = snapshot
        self._star_snapshot_profile = self._current_profile_name() if snapshot is not None else None
        self.redraw()

    def set_star_visibility(self, *, stars: bool, constellations: bool) -> None:
        self._show_stars = stars
        self._show_constellations = constellations
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        snapshot = self._star_snapshot
        if snapshot is None:
            return

        # A star snapshot belongs to the observer profile that was selected when
        # it was installed. If the user changes location, suppress that old sky
        # immediately while the replacement snapshot is being calculated.
        if self._star_snapshot_profile != self._current_profile_name():
            return

        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)

        if self._show_constellations:
            for line in snapshot.constellation_lines:
                start = project_live_view(
                    line.start_azimuth_deg,
                    line.start_elevation_deg,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=self.minimum_elevation_deg,
                    maximum_elevation_deg=self.maximum_elevation_deg,
                )
                end = project_live_view(
                    line.end_azimuth_deg,
                    line.end_elevation_deg,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=self.minimum_elevation_deg,
                    maximum_elevation_deg=self.maximum_elevation_deg,
                )
                if not start.visible or not end.visible:
                    continue
                self.create_line(
                    left + start.x_fraction * plot_width,
                    top + start.y_fraction * plot_height,
                    left + end.x_fraction * plot_width,
                    top + end.y_fraction * plot_height,
                    fill="#475569",
                    width=1,
                    tags=("constellation-line",),
                )

        if self._show_stars:
            for star in snapshot.stars:
                projection = project_live_view(
                    star.azimuth_deg,
                    star.elevation_deg,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=self.minimum_elevation_deg,
                    maximum_elevation_deg=self.maximum_elevation_deg,
                )
                if not projection.visible:
                    continue
                x = left + projection.x_fraction * plot_width
                y = top + projection.y_fraction * plot_height
                self._draw_star(star, x, y)

        # The stellar layer is reference scenery. Keep it behind the Live view
        # grid, satellite tracks, labels, and clickable satellite markers.
        self.tag_lower("star-field")
        self.tag_lower("constellation-line")

    def _draw_star(self, star: StarPoint, x: float, y: float) -> None:
        radius = star_marker_radius(star.magnitude)
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#e2e8f0",
            outline="",
            tags=("star-field",),
        )

        # Avoid a wall of labels at wide FOV. Zooming in progressively reveals
        # more named stars, which makes the layer useful as an observing guide.
        label_limit = 1.5 if self.horizontal_fov_deg > 45.0 else 3.0
        if star.name and star.magnitude <= label_limit:
            self.create_text(
                x + 5,
                y - 5,
                text=star.name,
                fill="#94a3b8",
                anchor="sw",
                font=("Segoe UI", 7),
                tags=("star-field",),
            )
