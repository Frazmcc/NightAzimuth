from __future__ import annotations

import tkinter as tk

from .sky_map import SkySatellite
from .star_field import StarPoint
from .star_live_view import is_vega_star, star_visual_style, vega_locator_text
from .terrain_star_live_view import TerrainStarLiveSkyView


class HudFinderView(TerrainStarLiveSkyView):
    """Sparse forward-looking sky HUD designed for real-world observing."""

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        grid = "#14532d"
        bright = "#22c55e"
        muted = "#4ade80"
        width = right - left
        height = bottom - top

        self.create_rectangle(left, top, right, bottom, outline=grid, width=1)

        # Sparse finder grid: quarter divisions rather than dense chart lines.
        for fraction in (0.25, 0.5, 0.75):
            x = left + width * fraction
            y = top + height * fraction
            self.create_line(x, top, x, bottom, fill=grid, dash=(2, 5))
            self.create_line(left, y, right, y, fill=grid, dash=(2, 5))

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
            right,
            top - 10,
            text=f"AZ {self.facing_deg:.0f}°  FOV {self.horizontal_fov_deg:.0f}°",
            fill=muted,
            anchor="e",
            font=("Segoe UI", 8),
        )
        self.create_text(
            (left + right) / 2,
            bottom + 18,
            text="LIVE FINDER",
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
            # Keep the background useful but quiet. Only reasonably bright stars
            # are drawn and they are deliberately small and unlabelled.
            if star.magnitude > 3.5 and not selected:
                return
            radius = 1.0 if star.magnitude > 2.0 else 1.5
            if selected:
                radius = 3.0
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="#94a3b8" if not selected else "#e2e8f0",
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
        if not satellite.potentially_visible and not selected:
            return

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
        if not satellite.potentially_visible and satellite.norad_id != self.selected_norad:
            return
        super()._draw_track(satellite, left, top, right, bottom)
