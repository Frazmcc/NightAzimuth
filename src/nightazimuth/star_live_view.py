from __future__ import annotations

from .live_view import LiveSkyView, project_live_view
from .star_field import PlanetPoint, StarFieldSnapshot, StarPoint


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


def automatic_star_label_limit(horizontal_fov_deg: float) -> float:
    """Reveal progressively more named stars as the observer narrows the view."""
    if horizontal_fov_deg > 120.0:
        return 2.0
    if horizontal_fov_deg > 60.0:
        return 3.0
    if horizontal_fov_deg > 30.0:
        return 4.0
    return 5.0


class StarLiveSkyView(LiveSkyView):
    """LiveSkyView with real stellar and planetary reference layers."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._star_snapshot: StarFieldSnapshot | None = None
        self._star_snapshot_profile: str | None = None
        self._show_stars = True
        self._show_constellations = False
        self._selected_star_hip: int | None = None
        self._selected_planet: str | None = None
        super().__init__(*args, **kwargs)

    def _current_profile_name(self) -> str | None:
        """Return the currently selected observer profile from the owning app."""
        selected = getattr(self.winfo_toplevel(), "selected_name", None)
        return str(selected) if selected else None

    def set_star_field(self, snapshot: StarFieldSnapshot | None) -> None:
        self._star_snapshot = snapshot
        self._star_snapshot_profile = self._current_profile_name() if snapshot is not None else None
        if snapshot is None:
            self._selected_star_hip = None
            self._selected_planet = None
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

            for planet in snapshot.planets:
                projection = project_live_view(
                    planet.azimuth_deg,
                    planet.elevation_deg,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=self.minimum_elevation_deg,
                    maximum_elevation_deg=self.maximum_elevation_deg,
                )
                if not projection.visible:
                    continue
                x = left + projection.x_fraction * plot_width
                y = top + projection.y_fraction * plot_height
                self._draw_planet(planet, x, y)

        # Keep celestial reference layers underneath satellites and their tracks.
        self.tag_lower("planet-field")
        self.tag_lower("star-field")
        self.tag_lower("constellation-line")

    def _draw_star(self, star: StarPoint, x: float, y: float) -> None:
        radius = star_marker_radius(star.magnitude)
        selected = star.hip_id == self._selected_star_hip
        tag = f"star:{star.hip_id}"
        hit_radius = max(radius + 4.0, 6.0)

        self.create_oval(
            x - hit_radius,
            y - hit_radius,
            x + hit_radius,
            y + hit_radius,
            fill="",
            outline="",
            tags=(tag, "star-field"),
        )
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#e2e8f0",
            outline="#ffffff" if selected else "",
            width=1,
            tags=(tag, "star-field"),
        )

        # Named stars provide the observer with useful visual landmarks. At a
        # wide view we keep only the brighter names; zooming in progressively
        # reveals more. Unnamed/fainter objects remain click-to-identify.
        label_limit = automatic_star_label_limit(self.horizontal_fov_deg)
        automatic_label = bool(star.name and star.magnitude <= label_limit)
        if automatic_label or selected:
            name = star.name or f"HIP {star.hip_id}"
            label = name
            if selected:
                label += f"  (mag {star.magnitude:.2f})"
            self.create_text(
                x + 5,
                y - 5,
                text=label,
                fill="#cbd5e1" if selected else "#94a3b8",
                anchor="sw",
                font=("Segoe UI", 8 if selected else 7, "bold" if selected else "normal"),
                tags=(tag, "star-field"),
            )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=star: self._select_star(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_planet(self, planet: PlanetPoint, x: float, y: float) -> None:
        selected = planet.name == self._selected_planet
        radius = 5.0 if selected else 4.0
        tag = f"planet:{planet.name}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#f8fafc",
            outline="#ffffff",
            width=2 if selected else 1,
            tags=(tag, "planet-field"),
        )
        self.create_text(
            x + 7,
            y - 6,
            text=planet.name,
            fill="#f8fafc",
            anchor="sw",
            font=("Segoe UI", 8, "bold"),
            tags=(tag, "planet-field"),
        )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=planet: self._select_planet(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _select_star(self, star: StarPoint) -> None:
        self._selected_star_hip = None if self._selected_star_hip == star.hip_id else star.hip_id
        self._selected_planet = None
        self.redraw()

    def _select_planet(self, planet: PlanetPoint) -> None:
        self._selected_planet = None if self._selected_planet == planet.name else planet.name
        self._selected_star_hip = None
        self.redraw()
