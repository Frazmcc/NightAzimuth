from __future__ import annotations

import tkinter as tk

from .live_view import project_live_view
from .sky_map import SkySatellite
from .star_field import StarPoint
from .star_live_view import is_vega_star, star_visual_style, vega_locator_text
from .terrain_star_live_view import TerrainStarLiveSkyView


def select_finder_satellites(
    satellites: list[SkySatellite],
    *,
    selected_norad: str | None = None,
    limit: int = 10,
    show_all: bool = False,
) -> list[SkySatellite]:
    """Choose a sparse set of live-finder candidates without a hard range cutoff."""
    if show_all:
        chosen = [satellite for satellite in satellites if satellite.potentially_visible]
    else:
        chosen = sorted(
            (satellite for satellite in satellites if satellite.potentially_visible),
            key=lambda satellite: (-satellite.elevation_deg, satellite.range_km),
        )[: max(1, int(limit))]

    if selected_norad is not None and all(satellite.norad_id != selected_norad for satellite in chosen):
        selected = next((satellite for satellite in satellites if satellite.norad_id == selected_norad), None)
        if selected is not None:
            chosen.append(selected)
    return chosen


def pan_live_view_window(
    *,
    facing_deg: float,
    minimum_elevation_deg: float,
    maximum_elevation_deg: float,
    horizontal_fov_deg: float,
    delta_x_fraction: float,
    delta_y_fraction: float,
) -> tuple[float, float, float]:
    """Pan a live-view window while keeping elevation inside the real 0..90° sky."""
    new_facing = (facing_deg - delta_x_fraction * horizontal_fov_deg) % 360.0
    span = max(1.0, maximum_elevation_deg - minimum_elevation_deg)
    elevation_shift = delta_y_fraction * span
    new_min = minimum_elevation_deg + elevation_shift
    new_max = maximum_elevation_deg + elevation_shift

    if new_min < 0.0:
        new_max -= new_min
        new_min = 0.0
    if new_max > 90.0:
        new_min -= new_max - 90.0
        new_max = 90.0

    return new_facing, max(0.0, new_min), min(90.0, new_max)


class HudFinderView(TerrainStarLiveSkyView):
    """Sparse forward-looking sky HUD designed for real-world observing."""

    DEFAULT_CANDIDATE_LIMIT = 10

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._all_satellites: list[SkySatellite] = []
        self._show_all_tracked = False
        self._pan_start: tuple[float, float] | None = None
        self._pan_origin: tuple[float, float, float] | None = None
        super().__init__(*args, **kwargs)

        # The finder is for a person looking from horizon to zenith. Replace the
        # older rectangle-to-zoom drag gesture with direct click-and-drag panning.
        self.bind("<ButtonPress-1>", self._on_pan_start)
        self.bind("<B1-Motion>", self._on_pan_motion)
        self.bind("<ButtonRelease-1>", self._on_pan_end)
        self.reset_zoom()

    @property
    def finder_candidate_count(self) -> int:
        return len(self._satellites)

    def reset_zoom(self) -> None:
        self._facing_deg = self._base_facing_deg
        self._horizontal_fov_deg = self._base_horizontal_fov_deg
        self._minimum_elevation_deg = 0.0
        self._maximum_elevation_deg = 90.0
        self.redraw()

    def _zoom_about(self, factor: float, x_fraction: float, y_fraction: float) -> None:
        old_fov = self._horizontal_fov_deg
        new_fov = max(5.0, min(self._base_horizontal_fov_deg, old_fov * factor))
        horizontal_offset = (x_fraction - 0.5) * old_fov
        self._facing_deg = (self._facing_deg + horizontal_offset * (1.0 - factor)) % 360.0
        self._horizontal_fov_deg = new_fov

        old_min = self._minimum_elevation_deg
        old_max = self._maximum_elevation_deg
        old_span = old_max - old_min
        new_span = max(5.0, min(90.0, old_span * factor))
        cursor_elevation = old_max - y_fraction * old_span
        new_max = cursor_elevation + y_fraction * new_span
        new_min = new_max - new_span
        if new_min < 0.0:
            new_max -= new_min
            new_min = 0.0
        if new_max > 90.0:
            new_min -= new_max - 90.0
            new_max = 90.0
        self._minimum_elevation_deg = max(0.0, new_min)
        self._maximum_elevation_deg = min(90.0, new_max)
        self.redraw()

    def _on_pan_start(self, event: tk.Event) -> None:
        if self.find_withtag("current"):
            current_tags = self.gettags("current")
            if any(
                tag.startswith(("live-sat:", "star:", "planet:"))
                for tag in current_tags
            ):
                self._pan_start = None
                self._pan_origin = None
                return
        left, top, right, bottom = self._plot_bounds()
        if not (left <= event.x <= right and top <= event.y <= bottom):
            return
        self._pan_start = (float(event.x), float(event.y))
        self._pan_origin = (
            self._facing_deg,
            self._minimum_elevation_deg,
            self._maximum_elevation_deg,
        )
        self.config(cursor="fleur")

    def _on_pan_motion(self, event: tk.Event) -> None:
        if self._pan_start is None or self._pan_origin is None:
            return
        left, top, right, bottom = self._plot_bounds()
        width = max(right - left, 1.0)
        height = max(bottom - top, 1.0)
        start_x, start_y = self._pan_start
        delta_x_fraction = (float(event.x) - start_x) / width
        delta_y_fraction = (float(event.y) - start_y) / height
        origin_facing, origin_min, origin_max = self._pan_origin
        facing, minimum, maximum = pan_live_view_window(
            facing_deg=origin_facing,
            minimum_elevation_deg=origin_min,
            maximum_elevation_deg=origin_max,
            horizontal_fov_deg=self._horizontal_fov_deg,
            delta_x_fraction=delta_x_fraction,
            delta_y_fraction=delta_y_fraction,
        )
        self._facing_deg = facing
        self._minimum_elevation_deg = minimum
        self._maximum_elevation_deg = maximum
        self.redraw()
        self.config(cursor="fleur")

    def _on_pan_end(self, _event: tk.Event) -> None:
        self._pan_start = None
        self._pan_origin = None
        self.config(cursor="")

    def set_show_all_tracked(self, show_all: bool) -> None:
        self._show_all_tracked = bool(show_all)
        self._rebuild_display_satellites()

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        self._all_satellites = list(satellites)
        if self._selected_norad not in {sat.norad_id for sat in satellites}:
            self._selected_norad = None
        self._rebuild_display_satellites()

    def select_norad(self, norad_id: str | None) -> None:
        self._selected_norad = norad_id
        self._rebuild_display_satellites()

    def _rebuild_display_satellites(self) -> None:
        self._satellites = select_finder_satellites(
            self._all_satellites,
            selected_norad=self._selected_norad,
            limit=self.DEFAULT_CANDIDATE_LIMIT,
            show_all=self._show_all_tracked,
        )
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        for item in self.find_all():
            if self.type(item) != "text":
                continue
            text = str(self.itemcget(item, "text"))
            if "above current elevation view" in text:
                self.delete(item)

        left, top, right, _bottom = self._plot_bounds()
        self.create_text(
            right - 6,
            top - 10,
            text=f"{self._visible_candidate_count()} finder candidate(s)",
            fill="#4ade80",
            anchor="e",
            font=("Segoe UI", 8),
            tags=("finder-candidate-count",),
        )

    def _visible_candidate_count(self) -> int:
        count = 0
        for satellite in self._satellites:
            projection = project_live_view(
                satellite.azimuth_deg,
                satellite.elevation_deg,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            if projection.visible:
                count += 1
        return count

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        grid = "#0f3d25"
        bright = "#22c55e"
        muted = "#4ade80"
        width = right - left
        height = bottom - top

        self.create_rectangle(left, top, right, bottom, outline=grid, width=1)

        for fraction in (0.25, 0.5, 0.75):
            x = left + width * fraction
            y = top + height * fraction
            self.create_line(x, top, x, bottom, fill=grid, dash=(2, 7))
            self.create_line(left, y, right, y, fill=grid, dash=(2, 7))

        minimum = self.minimum_elevation_deg
        maximum = self.maximum_elevation_deg
        self.create_text(
            left,
            top - 10,
            text=f"EL {minimum:.0f}–{maximum:.0f}°",
            fill=muted,
            anchor="w",
            font=("Segoe UI", 8),
        )
        self.create_text(
            left,
            bottom + 18,
            text=f"AZ {self.facing_deg:.0f}°  FOV {self.horizontal_fov_deg:.0f}°",
            fill=muted,
            anchor="w",
            font=("Segoe UI", 8),
        )
        self.create_text(
            (left + right) / 2,
            bottom + 18,
            text="DRAG TO LOOK AROUND  •  WHEEL TO ZOOM",
            fill=bright,
            font=("Segoe UI", 8, "bold"),
        )

    def _draw_star(self, star: StarPoint, x: float, y: float) -> None:
        selected = star.hip_id == self._selected_star_hip
        style = star_visual_style(star, selected=selected)
        tag = f"star:{star.hip_id}"

        if is_vega_star(star):
            radius = max(style.radius, 5.0)
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="#dbeafe",
                outline="#60a5fa",
                width=2,
                tags=(tag, "star-field"),
            )
            self.create_text(
                x + 8,
                y - 8,
                text=vega_locator_text(star),
                fill="#93c5fd",
                anchor="sw",
                font=("Segoe UI", 9, "bold"),
                tags=(tag, "star-field"),
            )
        else:
            if star.magnitude > 3.0 and not selected:
                return
            radius = 0.8 if star.magnitude > 2.0 else 1.2
            if selected:
                radius = 3.0
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="#64748b" if not selected else "#e2e8f0",
                outline="",
                tags=(tag, "star-field"),
            )
            if selected:
                name = star.name or f"HIP {star.hip_id}"
                self.create_text(
                    x + 6,
                    y - 6,
                    text=f"{name}  mag {star.magnitude:.2f}",
                    fill="#cbd5e1",
                    anchor="sw",
                    font=("Segoe UI", 8),
                    tags=(tag, "star-field"),
                )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=star: self._select_star(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        selected = satellite.norad_id == self.selected_norad
        radius = 6 if selected else 3
        fill = "#22c55e" if satellite.potentially_visible else "#60a5fa"
        tag = f"live-sat:{satellite.norad_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline="#ffffff" if selected else fill,
            width=2 if selected else 1,
            tags=(tag, "live-satellite"),
        )
        if selected:
            self.create_text(
                x + 8,
                y - 8,
                text=f"{satellite.name}  Az {satellite.azimuth_deg:.0f}°  El {satellite.elevation_deg:.0f}°",
                fill="#bbf7d0",
                anchor="sw",
                font=("Segoe UI", 8, "bold"),
                tags=(tag,),
            )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_track(
        self,
        satellite: SkySatellite,
        left: float,
        top: float,
        right: float,
        bottom: float,
    ) -> None:
        if satellite.norad_id != self.selected_norad:
            return
        super()._draw_track(satellite, left, top, right, bottom)
