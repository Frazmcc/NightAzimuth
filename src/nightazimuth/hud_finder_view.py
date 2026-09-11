from __future__ import annotations

import tkinter as tk

from .sky_map import SkySatellite
from .star_field import StarPoint
from .star_live_view import is_vega_star, star_visual_style, vega_locator_text
from .terrain_star_live_view import TerrainStarLiveSkyView


def select_finder_satellites(
    satellites: list[SkySatellite],
    *,
    selected_norad: str | None = None,
    limit: int = 1,
    show_all: bool = False,
) -> list[SkySatellite]:
    """Choose the live-sky target set without applying a hard range cutoff."""
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


class HudFinderView(TerrainStarLiveSkyView):
    """Sparse forward-looking live sky focused on one observing target."""

    DEFAULT_CANDIDATE_LIMIT = 1

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._all_satellites: list[SkySatellite] = []
        self._show_all_tracked = False
        super().__init__(*args, **kwargs)

    @property
    def finder_candidate_count(self) -> int:
        return len(self._satellites)

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

    def _primary_target_norad(self) -> str | None:
        if self._selected_norad is not None:
            return self._selected_norad
        if self._satellites:
            return self._satellites[0].norad_id
        return None

    def redraw(self) -> None:
        super().redraw()
        for item in self.find_all():
            if self.type(item) != "text":
                continue
            text = str(self.itemcget(item, "text"))
            if "above current elevation view" in text:
                self.delete(item)

        left, top, right, _bottom = self._plot_bounds()
        primary = self._primary_target_norad()
        self.create_text(
            right - 6,
            top - 10,
            text="LIVE TARGET" if primary is not None else "NO LIVE TARGET",
            fill="#4ade80",
            anchor="e",
            font=("Segoe UI", 8, "bold"),
            tags=("finder-target-status",),
        )

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        grid = "#0b2f20"
        bright = "#22c55e"
        muted = "#3fa66a"
        width = right - left
        height = bottom - top

        self.create_rectangle(left, top, right, bottom, outline=grid, width=1)
        for fraction in (0.25, 0.5, 0.75):
            x = left + width * fraction
            y = top + height * fraction
            self.create_line(x, top, x, bottom, fill=grid, dash=(2, 9))
            self.create_line(left, y, right, y, fill=grid, dash=(2, 9))

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
            text="LIVE SKY",
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
            radius = 0.7 if star.magnitude > 2.0 else 1.1
            if selected:
                radius = 3.0
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="#526174" if not selected else "#e2e8f0",
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
        primary = satellite.norad_id == self._primary_target_norad()
        selected = satellite.norad_id == self.selected_norad
        radius = 7 if primary else 3
        fill = "#fbbf24" if primary else "#22c55e"
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
        if primary:
            self.create_text(
                x + 9,
                y - 9,
                text=f"{satellite.name}  Az {satellite.azimuth_deg:.0f}°  El {satellite.elevation_deg:.0f}°",
                fill="#fde68a",
                anchor="sw",
                font=("Segoe UI", 9, "bold"),
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
        if satellite.norad_id != self._primary_target_norad():
            return
        super()._draw_track(satellite, left, top, right, bottom)
