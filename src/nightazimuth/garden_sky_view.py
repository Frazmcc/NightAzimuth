from __future__ import annotations

import math
import tkinter as tk
from typing import Callable

from .sky_map import SkySatellite
from .star_field import PlanetPoint, StarFieldSnapshot, StarPoint
from .star_live_view import is_vega_star, star_visual_style, vega_locator_text
from .terrain_horizon import HorizonPoint


def project_garden_sky(
    azimuth_deg: float,
    elevation_deg: float,
    *,
    center_x: float,
    center_y: float,
    radius: float,
) -> tuple[float, float]:
    """Project a true azimuth/elevation position onto an observer-centred sky dome.

    The horizon is the outside circle and the zenith is the centre. North is at
    the top, east at the right, south at the bottom and west at the left.
    """
    elevation = max(0.0, min(90.0, float(elevation_deg)))
    azimuth = math.radians(float(azimuth_deg) % 360.0)
    radial = radius * (90.0 - elevation) / 90.0
    return (
        center_x + radial * math.sin(azimuth),
        center_y - radial * math.cos(azimuth),
    )


class GardenSkyDomeView(tk.Canvas):
    """Human-style all-sky view for an observer standing outside and looking up."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[SkySatellite], None] | None = None,
        **kwargs: object,
    ) -> None:
        kwargs.setdefault("background", "#08111f")
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self._satellites: list[SkySatellite] = []
        self._selected_norad: str | None = None
        self._star_snapshot: StarFieldSnapshot | None = None
        self._star_snapshot_profile: str | None = None
        self._show_stars = True
        self._show_constellations = False
        self._selected_star_hip: int | None = None
        self._selected_planet: str | None = None
        self._terrain_horizon: tuple[HorizonPoint, ...] = ()
        self._terrain_status = "Terrain: waiting for location"
        self._facing_deg = 0.0
        self._on_select = on_select
        self.bind("<Configure>", lambda _event: self.redraw())

    @property
    def facing_deg(self) -> float:
        return self._facing_deg

    @property
    def horizontal_fov_deg(self) -> float:
        return 360.0

    @property
    def minimum_elevation_deg(self) -> float:
        return 0.0

    @property
    def maximum_elevation_deg(self) -> float:
        return 90.0

    @property
    def selected_norad(self) -> str | None:
        return self._selected_norad

    def _current_profile_name(self) -> str | None:
        selected = getattr(self.winfo_toplevel(), "selected_name", None)
        return str(selected) if selected else None

    def set_view(self, facing_deg: float, _horizontal_fov_deg: float) -> None:
        """Set only the observer-facing direction marker; the entire sky stays visible."""
        self._facing_deg = float(facing_deg) % 360.0
        self.redraw()

    def zoom_in(self) -> None:
        self.redraw()

    def zoom_out(self) -> None:
        self.redraw()

    def reset_zoom(self) -> None:
        self.redraw()

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        self._satellites = satellites
        if self._selected_norad not in {sat.norad_id for sat in satellites}:
            self._selected_norad = None
        self.redraw()

    def select_norad(self, norad_id: str | None) -> None:
        self._selected_norad = norad_id
        self.redraw()

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

    def set_terrain_horizon(self, horizon: tuple[HorizonPoint, ...] | None) -> None:
        self._terrain_horizon = horizon or ()
        self.redraw()

    def set_terrain_status(self, status: str) -> None:
        self._terrain_status = status
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        radius = max(min(width - 120.0, height - 90.0) / 2.0, 40.0)
        cx = width / 2.0
        cy = height / 2.0 + 8.0

        self._draw_dome_grid(cx, cy, radius)

        snapshot = self._star_snapshot
        if snapshot is not None and self._star_snapshot_profile == self._current_profile_name():
            if self._show_constellations:
                self._draw_constellations(snapshot, cx, cy, radius)
            if self._show_stars:
                self._draw_stars(snapshot, cx, cy, radius)
            self._draw_planets(snapshot, cx, cy, radius)

        for satellite in self._satellites:
            self._draw_track(satellite, cx, cy, radius)
        for satellite in self._satellites:
            if satellite.elevation_deg >= 0.0:
                self._draw_satellite(satellite, cx, cy, radius)

        # Terrain is deliberately drawn after sky objects so anything below the
        # calculated local skyline is hidden, matching the observer's real view.
        if self._terrain_horizon:
            self._draw_terrain(cx, cy, radius)

        self._draw_facing_marker(cx, cy, radius)
        self.create_text(
            width - 12,
            12,
            text=self._terrain_status,
            fill="#94a3b8",
            anchor="ne",
            font=("Segoe UI", 8),
            tags=("terrain-status",),
        )

    def _draw_dome_grid(self, cx: float, cy: float, radius: float) -> None:
        grid = "#334155"
        muted = "#94a3b8"
        bright = "#dbeafe"
        self.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#64748b", width=2)
        for elevation in (30.0, 60.0):
            ring = radius * (90.0 - elevation) / 90.0
            self.create_oval(cx - ring, cy - ring, cx + ring, cy + ring, outline=grid, width=1)
            self.create_text(cx + 6, cy - ring + 10, text=f"{elevation:.0f}°", fill=muted, anchor="w", font=("Segoe UI", 8))
        self.create_line(cx - radius, cy, cx + radius, cy, fill=grid)
        self.create_line(cx, cy - radius, cx, cy + radius, fill=grid)
        offset = 18
        self.create_text(cx, cy - radius - offset, text="N", fill=bright, font=("Segoe UI", 11, "bold"))
        self.create_text(cx + radius + offset, cy, text="E", fill=bright, font=("Segoe UI", 11, "bold"))
        self.create_text(cx, cy + radius + offset, text="S", fill=bright, font=("Segoe UI", 11, "bold"))
        self.create_text(cx - radius - offset, cy, text="W", fill=bright, font=("Segoe UI", 11, "bold"))
        self.create_text(cx, cy + 10, text="ZENITH\n90°", fill=muted, justify="center", font=("Segoe UI", 8, "bold"))
        self.create_text(cx, cy + radius + 32, text="HORIZON • 0° ELEVATION • FULL 360° AROUND OBSERVER", fill=muted, font=("Segoe UI", 8))

    def _draw_constellations(self, snapshot: StarFieldSnapshot, cx: float, cy: float, radius: float) -> None:
        for line in snapshot.constellation_lines:
            if line.start_elevation_deg < 0.0 or line.end_elevation_deg < 0.0:
                continue
            x1, y1 = project_garden_sky(line.start_azimuth_deg, line.start_elevation_deg, center_x=cx, center_y=cy, radius=radius)
            x2, y2 = project_garden_sky(line.end_azimuth_deg, line.end_elevation_deg, center_x=cx, center_y=cy, radius=radius)
            self.create_line(x1, y1, x2, y2, fill="#475569", width=1, tags=("constellation-line",))

    def _draw_stars(self, snapshot: StarFieldSnapshot, cx: float, cy: float, radius: float) -> None:
        vega: StarPoint | None = None
        for star in snapshot.stars:
            if star.elevation_deg < 0.0:
                continue
            if is_vega_star(star):
                vega = star
            x, y = project_garden_sky(star.azimuth_deg, star.elevation_deg, center_x=cx, center_y=cy, radius=radius)
            self._draw_star(star, x, y)
        if vega is not None:
            self.create_text(
                12,
                12,
                text=vega_locator_text(vega),
                fill="#93c5fd",
                anchor="nw",
                font=("Segoe UI", 9, "bold"),
                tags=("vega-locator",),
            )

    def _draw_star(self, star: StarPoint, x: float, y: float) -> None:
        selected = star.hip_id == self._selected_star_hip
        style = star_visual_style(star, selected=selected)
        tag = f"star:{star.hip_id}"
        self.create_oval(
            x - style.radius,
            y - style.radius,
            x + style.radius,
            y + style.radius,
            fill=style.fill,
            outline=style.outline,
            width=2 if is_vega_star(star) else 1,
            tags=(tag, "star-field"),
        )
        label = None
        if is_vega_star(star):
            label = vega_locator_text(star)
        elif selected:
            label = (star.name or f"HIP {star.hip_id}") + f"  (mag {star.magnitude:.2f})"
        elif star.name and star.magnitude <= 2.5:
            label = star.name
        if label:
            self.create_text(
                x + (7 if is_vega_star(star) else 5),
                y - (7 if is_vega_star(star) else 5),
                text=label,
                fill=style.label_fill,
                anchor="sw",
                font=("Segoe UI", 9 if is_vega_star(star) else 7, "bold" if (selected or is_vega_star(star)) else "normal"),
                tags=(tag, "star-field"),
            )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=star: self._select_star(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_planets(self, snapshot: StarFieldSnapshot, cx: float, cy: float, radius: float) -> None:
        for planet in snapshot.planets:
            if planet.elevation_deg < 0.0:
                continue
            x, y = project_garden_sky(planet.azimuth_deg, planet.elevation_deg, center_x=cx, center_y=cy, radius=radius)
            self._draw_planet(planet, x, y)

    def _draw_planet(self, planet: PlanetPoint, x: float, y: float) -> None:
        selected = planet.name == self._selected_planet
        r = 5.0 if selected else 4.0
        tag = f"planet:{planet.name}"
        self.create_oval(x - r, y - r, x + r, y + r, fill="#f8fafc", outline="#ffffff", width=2 if selected else 1, tags=(tag, "planet-field"))
        self.create_text(x + 7, y - 6, text=planet.name, fill="#f8fafc", anchor="sw", font=("Segoe UI", 8, "bold"), tags=(tag, "planet-field"))
        self.tag_bind(tag, "<Button-1>", lambda _event, item=planet: self._select_planet(item))

    def _draw_track(self, satellite: SkySatellite, cx: float, cy: float, radius: float) -> None:
        points = [point for point in satellite.future_track if point.elevation_deg >= 0.0]
        if len(points) < 2:
            return
        coords: list[float] = []
        for point in points:
            x, y = project_garden_sky(point.azimuth_deg, point.elevation_deg, center_x=cx, center_y=cy, radius=radius)
            coords.extend((x, y))
        colour = "#fbbf24" if satellite.potentially_visible else "#60a5fa"
        self.create_line(*coords, fill=colour, width=2 if satellite.norad_id == self._selected_norad else 1, dash=(4, 3), arrow=tk.LAST, arrowshape=(8, 10, 4), tags=("projected-track",))

    def _draw_satellite(self, satellite: SkySatellite, cx: float, cy: float, radius: float) -> None:
        x, y = project_garden_sky(satellite.azimuth_deg, satellite.elevation_deg, center_x=cx, center_y=cy, radius=radius)
        selected = satellite.norad_id == self._selected_norad
        r = 7 if selected else 5
        fill = "#fbbf24" if satellite.potentially_visible else "#60a5fa"
        tag = f"live-sat:{satellite.norad_id}"
        self.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="#ffffff" if selected else fill, width=2 if selected else 1, tags=(tag, "live-satellite"))
        self.create_text(x + 9, y - 9, text=satellite.name, fill="#dbeafe", anchor="sw", font=("Segoe UI", 8), tags=(tag,))
        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select_satellite(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_terrain(self, cx: float, cy: float, radius: float) -> None:
        points = sorted(self._terrain_horizon, key=lambda point: point.azimuth_deg)
        if len(points) < 3:
            return
        outer: list[tuple[float, float]] = []
        inner: list[tuple[float, float]] = []
        for point in points:
            outer.append(project_garden_sky(point.azimuth_deg, 0.0, center_x=cx, center_y=cy, radius=radius))
            inner.append(project_garden_sky(point.azimuth_deg, max(0.0, point.elevation_deg), center_x=cx, center_y=cy, radius=radius))
        polygon = outer + list(reversed(inner))
        flattened = [coord for point in polygon for coord in point]
        skyline = [coord for point in inner for coord in point]
        self.create_polygon(*flattened, fill="#182433", outline="", tags=("terrain-horizon",))
        self.create_line(*skyline, fill="#8fa77a", width=2, smooth=False, tags=("terrain-horizon",))

    def _draw_facing_marker(self, cx: float, cy: float, radius: float) -> None:
        inner_x, inner_y = project_garden_sky(self._facing_deg, 10.0, center_x=cx, center_y=cy, radius=radius)
        outer_x, outer_y = project_garden_sky(self._facing_deg, 0.0, center_x=cx, center_y=cy, radius=radius)
        self.create_line(inner_x, inner_y, outer_x, outer_y, fill="#22d3ee", width=3, arrow=tk.LAST, arrowshape=(10, 12, 5), tags=("facing-marker",))
        label_x, label_y = project_garden_sky(self._facing_deg, 4.0, center_x=cx, center_y=cy, radius=radius)
        self.create_text(label_x, label_y, text=f"Facing {self._facing_deg:.0f}°", fill="#67e8f9", font=("Segoe UI", 8, "bold"), tags=("facing-marker",))

    def _select_satellite(self, satellite: SkySatellite) -> None:
        self._selected_norad = satellite.norad_id
        self.redraw()
        if self._on_select is not None:
            self._on_select(satellite)

    def _select_star(self, star: StarPoint) -> None:
        self._selected_star_hip = None if self._selected_star_hip == star.hip_id else star.hip_id
        self._selected_planet = None
        self.redraw()

    def _select_planet(self, planet: PlanetPoint) -> None:
        self._selected_planet = None if self._selected_planet == planet.name else planet.name
        self._selected_star_hip = None
        self.redraw()
