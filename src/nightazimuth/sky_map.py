from __future__ import annotations

from dataclasses import dataclass
import math
import tkinter as tk
from typing import Callable

from .brightness import BrightnessEstimate
from .track_prediction import TrackPoint


@dataclass(frozen=True, slots=True)
class SkySatellite:
    name: str
    norad_id: str
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    satellite_sunlit: bool
    sky_dark: bool
    potentially_visible: bool
    twilight_candidate: bool = False
    phase_angle_deg: float | None = None
    brightness_estimate: BrightnessEstimate | None = None
    future_track: tuple[TrackPoint, ...] = ()


def project_sky_position(
    azimuth_deg: float,
    elevation_deg: float,
    *,
    center_x: float,
    center_y: float,
    radius: float,
) -> tuple[float, float]:
    """Project azimuth/elevation onto the all-sky radar view.

    Azimuth is measured clockwise from north. Elevation 0 degrees lies on the
    horizon circle and 90 degrees lies at the centre (zenith).
    """
    elevation = max(0.0, min(90.0, elevation_deg))
    azimuth = math.radians(azimuth_deg % 360.0)
    radial = radius * (90.0 - elevation) / 90.0
    return (
        center_x + radial * math.sin(azimuth),
        center_y - radial * math.cos(azimuth),
    )


class SkyMap(tk.Canvas):
    """Interactive radar-style all-sky view."""

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
        self._on_select = on_select
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        self._satellites = satellites
        if self._selected_norad not in {item.norad_id for item in satellites}:
            self._selected_norad = None
        self.redraw()

    def select_norad(self, norad_id: str | None) -> None:
        self._selected_norad = norad_id
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        cx = width / 2
        cy = height / 2
        radius = max(min(width, height) / 2 - 38, 20)

        self._draw_grid(cx, cy, radius)
        for satellite in self._satellites:
            self._draw_satellite(satellite, cx, cy, radius)

    def _draw_grid(self, cx: float, cy: float, radius: float) -> None:
        grid = "#334155"
        text = "#dbeafe"
        muted = "#94a3b8"

        for elevation in (0, 30, 60):
            ring_radius = radius * (90 - elevation) / 90
            self.create_oval(
                cx - ring_radius,
                cy - ring_radius,
                cx + ring_radius,
                cy + ring_radius,
                outline=grid,
                width=2 if elevation == 0 else 1,
            )
            if elevation:
                self.create_text(
                    cx + 6,
                    cy - ring_radius + 10,
                    text=f"{elevation}°",
                    fill=muted,
                    anchor="w",
                    font=("Segoe UI", 8),
                )

        self.create_line(cx - radius, cy, cx + radius, cy, fill=grid)
        self.create_line(cx, cy - radius, cx, cy + radius, fill=grid)

        label_offset = 17
        self.create_text(cx, cy - radius - label_offset, text="N", fill=text, font=("Segoe UI", 11, "bold"))
        self.create_text(cx + radius + label_offset, cy, text="E", fill=text, font=("Segoe UI", 11, "bold"))
        self.create_text(cx, cy + radius + label_offset, text="S", fill=text, font=("Segoe UI", 11, "bold"))
        self.create_text(cx - radius - label_offset, cy, text="W", fill=text, font=("Segoe UI", 11, "bold"))
        self.create_text(cx, cy + 10, text="ZENITH", fill=muted, font=("Segoe UI", 7))

    def _draw_satellite(
        self,
        satellite: SkySatellite,
        cx: float,
        cy: float,
        radius: float,
    ) -> None:
        x, y = project_sky_position(
            satellite.azimuth_deg,
            satellite.elevation_deg,
            center_x=cx,
            center_y=cy,
            radius=radius,
        )

        selected = satellite.norad_id == self._selected_norad
        marker_radius = 6 if selected else 4
        marker_fill = "#fbbf24" if satellite.potentially_visible else "#60a5fa"
        outline = "#ffffff" if selected else marker_fill
        width = 2 if selected else 1
        tag = f"sat:{satellite.norad_id}"

        self.create_oval(
            x - marker_radius,
            y - marker_radius,
            x + marker_radius,
            y + marker_radius,
            fill=marker_fill,
            outline=outline,
            width=width,
            tags=(tag, "satellite"),
        )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _select(self, satellite: SkySatellite) -> None:
        self._selected_norad = satellite.norad_id
        self.redraw()
        if self._on_select is not None:
            self._on_select(satellite)
