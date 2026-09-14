from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass

from .live_view import LiveSkyView, project_live_view
from .star_field import PlanetPoint, StarFieldSnapshot, StarPoint

VEGA_HIP_ID = 91262


@dataclass(frozen=True, slots=True)
class StarVisualStyle:
    radius: float
    fill: str
    outline: str
    label_fill: str
    force_label: bool = False


@dataclass(frozen=True, slots=True)
class ConstellationVisualStyle:
    """Canvas-compatible constellation styling for the active sky conditions."""

    fill: str
    width: int


CONSTELLATION_CONTRAST_MODES = ("Auto", "Subtle", "Strong")


def constellation_visual_style(
    sky_state_code: int,
    *,
    cloud_overlay_enabled: bool = False,
    contrast_mode: str = "Auto",
) -> ConstellationVisualStyle:
    """Return an adaptive line colour and width for the current Live-view background.

    Tk canvas lines do not support alpha transparency, so the palettes encode
    apparent opacity by blending the line colour toward each sky background.
    """

    try:
        state = max(0, min(4, int(sky_state_code)))
    except (TypeError, ValueError):
        state = 0
    mode = contrast_mode if contrast_mode in CONSTELLATION_CONTRAST_MODES else "Auto"

    subtle = {
        0: ConstellationVisualStyle("#334155", 1),
        1: ConstellationVisualStyle("#3f4b63", 1),
        2: ConstellationVisualStyle("#526987", 1),
        3: ConstellationVisualStyle("#6f8da8", 1),
        4: ConstellationVisualStyle("#233f52", 1),
    }
    automatic = {
        0: ConstellationVisualStyle("#64748b", 1),
        1: ConstellationVisualStyle("#7183a3", 1),
        2: ConstellationVisualStyle("#7dd3fc", 2),
        3: ConstellationVisualStyle("#bae6fd", 2),
        4: ConstellationVisualStyle("#102a3b", 2),
    }
    strong = {
        0: ConstellationVisualStyle("#cbd5e1", 2),
        1: ConstellationVisualStyle("#dbeafe", 2),
        2: ConstellationVisualStyle("#e0f2fe", 3),
        3: ConstellationVisualStyle("#f0f9ff", 3),
        4: ConstellationVisualStyle("#061827", 3),
    }

    if mode == "Subtle":
        return subtle[state]
    if mode == "Strong":
        return strong[state]
    if cloud_overlay_enabled:
        return strong[state]
    return automatic[state]


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


def is_vega_star(star: StarPoint) -> bool:
    """Return True for Vega using its Hipparcos identity or proper name."""
    return star.hip_id == VEGA_HIP_ID or (star.name or "").casefold() == "vega"


def vega_locator_text(star: StarPoint) -> str:
    """Return Vega's live compass heading and elevation for quick real-sky locating."""
    return f"VEGA  Az {star.azimuth_deg:.0f}\N{DEGREE SIGN}  El {star.elevation_deg:.0f}\N{DEGREE SIGN}"


def star_visual_style(star: StarPoint, *, selected: bool) -> StarVisualStyle:
    """Return rendering style, giving Vega a strong blue-white reference marker."""
    if is_vega_star(star):
        return StarVisualStyle(
            radius=5.0 if selected else 4.5,
            fill="#dbeafe",
            outline="#ffffff",
            label_fill="#bfdbfe" if selected else "#93c5fd",
            force_label=True,
        )

    return StarVisualStyle(
        radius=star_marker_radius(star.magnitude),
        fill="#e2e8f0",
        outline="#ffffff" if selected else "",
        label_fill="#cbd5e1" if selected else "#94a3b8",
    )


class StarLiveSkyView(LiveSkyView):
    """LiveSkyView with real stellar and planetary reference layers."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._star_snapshot: StarFieldSnapshot | None = None
        self._star_snapshot_profile: str | None = None
        self._show_stars = True
        self._show_constellations = False
        self._constellation_contrast = "Auto"
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

    def set_constellation_contrast(self, mode: str) -> None:
        """Select adaptive, subtle, or strong constellation visibility."""

        self._constellation_contrast = (
            mode if mode in CONSTELLATION_CONTRAST_MODES else "Auto"
        )
        self.redraw()

    def _current_constellation_style(self) -> ConstellationVisualStyle:
        snapshot = getattr(self.winfo_toplevel(), "_observing_snapshot", None)
        sky_state_code = getattr(snapshot, "sky_state_code", 0)
        return constellation_visual_style(
            sky_state_code,
            cloud_overlay_enabled=bool(getattr(self, "_show_cloud_overlay", False)),
            contrast_mode=self._constellation_contrast,
        )

    def refresh_constellation_style(self) -> None:
        """Restyle existing lines when the solar sky state changes."""

        if not self._show_constellations:
            return
        style = self._current_constellation_style()
        self.itemconfigure("constellation-line", fill=style.fill, width=style.width)

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
            constellation_style = self._current_constellation_style()
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
                    fill=constellation_style.fill,
                    width=constellation_style.width,
                    tags=("constellation-line",),
                )

        vega: StarPoint | None = None
        if self._show_stars:
            for star in snapshot.stars:
                if is_vega_star(star):
                    vega = star
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

            if vega is not None:
                self._draw_vega_locator(vega, left, top)

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

        label_limit = automatic_star_label_limit(self.horizontal_fov_deg)
        automatic_label = bool(star.name and star.magnitude <= label_limit)
        if automatic_label or style.force_label or selected:
            name = star.name or f"HIP {star.hip_id}"
            label = name
            if is_vega_star(star):
                label = vega_locator_text(star)
            if selected:
                label += f"  (mag {star.magnitude:.2f})"
            self.create_text(
                x + 7 if is_vega_star(star) else x + 5,
                y - 7 if is_vega_star(star) else y - 5,
                text=label,
                fill=style.label_fill,
                anchor="sw",
                font=(
                    "Segoe UI",
                    9 if is_vega_star(star) else (8 if selected else 7),
                    "bold" if (selected or is_vega_star(star)) else "normal",
                ),
                tags=(tag, "star-field"),
            )

    def _draw_vega_locator(self, star: StarPoint, left: float, top: float) -> None:
        """Show Vega's current heading even when it is outside the current Live view."""
        self.create_text(
            left + 8,
            top + 8,
            text=vega_locator_text(star),
            fill="#93c5fd",
            anchor="nw",
            font=("Segoe UI", 9, "bold"),
            tags=("vega-locator", "star-field"),
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
