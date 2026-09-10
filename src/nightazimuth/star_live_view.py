from __future__ import annotations

import math
import tkinter as tk

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
    """Return the faintest named-star magnitude labelled at the current zoom."""
    if horizontal_fov_deg > 120.0:
        return 2.0
    if horizontal_fov_deg > 75.0:
        return 3.0
    if horizontal_fov_deg > 45.0:
        return 3.5
    if horizontal_fov_deg > 25.0:
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
        self._celestial_press: tuple[float, float] | None = None
        self._drawn_star_positions: list[tuple[StarPoint, float, float]] = []
        super().__init__(*args, **kwargs)
        self.bind("<ButtonPress-1>", self._remember_celestial_press, add="+")
        self.bind("<ButtonRelease-1>", self._handle_celestial_click, add="+")

    def _current_profile_name(self) -> str | None:
        """Return the currently selected observer profile from the owning app."""
        selected = getattr(self.winfo_toplevel(), "selected_name", None)
        return str(selected) if selected else None

    def set_star_field(self, snapshot: StarFieldSnapshot | None) -> None:
        incoming_profile = self._current_profile_name() if snapshot is not None else None
        if incoming_profile != self._star_snapshot_profile:
            self._selected_star_hip = None
            self._selected_planet = None
        self._star_snapshot = snapshot
        self._star_snapshot_profile = incoming_profile
        self.redraw()

    def set_star_visibility(self, *, stars: bool, constellations: bool) -> None:
        self._show_stars = stars
        self._show_constellations = constellations
        if not stars:
            self._selected_star_hip = None
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        self._drawn_star_positions = []
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
                self._drawn_star_positions.append((star, x, y))
                self._draw_star(star, x, y)

        # Planets are intentionally independent of the Stars checkbox. Major
        # planets remain visible and labelled whenever they are inside the view.
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

    def _remember_celestial_press(self, event: tk.Event) -> None:
        self._celestial_press = (float(event.x), float(event.y))

    def _handle_celestial_click(self, event: tk.Event) -> None:
        press = self._celestial_press
        self._celestial_press = None
        if press is None:
            return
        if math.hypot(float(event.x) - press[0], float(event.y) - press[1]) > 6.0:
            return

        current_tags = self.gettags("current") if self.find_withtag("current") else ()
        if "projected-track" in current_tags or any(
            tag.startswith(("live-sat:", "planet:")) for tag in current_tags
        ):
            return
        if not self._show_stars:
            return

        nearest: tuple[StarPoint, float] | None = None
        for star, x, y in self._drawn_star_positions:
            distance = math.hypot(float(event.x) - x, float(event.y) - y)
            if distance <= 8.0 and (nearest is None or distance < nearest[1]):
                nearest = (star, distance)

        if nearest is not None:
            self._select_star(nearest[0])

    def _select_star(self, star: StarPoint) -> None:
        self._selected_star_hip = None if self._selected_star_hip == star.hip_id else star.hip_id
        self._selected_planet = None
        self.redraw()

    def _select_planet(self, planet: PlanetPoint) -> None:
        self._selected_planet = None if self._selected_planet == planet.name else planet.name
        self._selected_star_hip = None
        self.redraw()
