from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from typing import Callable

from .sky_map import SkySatellite


@dataclass(frozen=True, slots=True)
class LiveProjection:
    visible: bool
    x_fraction: float
    y_fraction: float


def signed_angular_difference(angle_deg: float, centre_deg: float) -> float:
    """Return shortest signed angular difference in degrees."""
    return (angle_deg - centre_deg + 180.0) % 360.0 - 180.0


def project_live_view(
    azimuth_deg: float,
    elevation_deg: float,
    facing_deg: float,
    horizontal_fov_deg: float,
) -> LiveProjection:
    """Project azimuth/elevation into a forward-looking rectangular sky view."""
    fov = max(10.0, min(180.0, horizontal_fov_deg))
    half_fov = fov / 2.0
    offset = signed_angular_difference(azimuth_deg, facing_deg)
    visible = abs(offset) <= half_fov and 0.0 <= elevation_deg <= 90.0
    x_fraction = 0.5 + offset / fov
    y_fraction = 1.0 - elevation_deg / 90.0
    return LiveProjection(visible, x_fraction, y_fraction)


class LiveSkyView(tk.Canvas):
    """Observer-facing view of the portion of sky currently being watched."""

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
        self._facing_deg = 0.0
        self._horizontal_fov_deg = 90.0
        self._on_select = on_select
        self.bind("<Configure>", lambda _event: self.redraw())

    @property
    def facing_deg(self) -> float:
        return self._facing_deg

    @property
    def horizontal_fov_deg(self) -> float:
        return self._horizontal_fov_deg

    def set_view(self, facing_deg: float, horizontal_fov_deg: float) -> None:
        self._facing_deg = facing_deg % 360.0
        self._horizontal_fov_deg = max(10.0, min(180.0, horizontal_fov_deg))
        self.redraw()

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        self._satellites = satellites
        if self._selected_norad not in {sat.norad_id for sat in satellites}:
            self._selected_norad = None
        self.redraw()

    def select_norad(self, norad_id: str | None) -> None:
        self._selected_norad = norad_id
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        left, right = 45.0, width - 24.0
        top, bottom = 28.0, height - 48.0
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)

        self._draw_grid(left, top, right, bottom)

        visible_count = 0
        for satellite in self._satellites:
            projection = project_live_view(
                satellite.azimuth_deg,
                satellite.elevation_deg,
                self._facing_deg,
                self._horizontal_fov_deg,
            )
            if not projection.visible:
                continue
            visible_count += 1
            x = left + projection.x_fraction * plot_width
            y = top + projection.y_fraction * plot_height
            self._draw_satellite(satellite, x, y)

        if visible_count == 0:
            self.create_text(
                (left + right) / 2,
                (top + bottom) / 2,
                text="No tracked satellites currently in this view",
                fill="#94a3b8",
                font=("Segoe UI", 11),
            )

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        grid = "#334155"
        text = "#dbeafe"
        muted = "#94a3b8"
        width = right - left
        height = bottom - top

        self.create_rectangle(left, top, right, bottom, outline=grid, width=2)

        for elevation in (0, 30, 60, 90):
            y = bottom - (elevation / 90.0) * height
            self.create_line(left, y, right, y, fill=grid)
            self.create_text(left - 8, y, text=f"{elevation}°", fill=muted, anchor="e", font=("Segoe UI", 8))

        half = self._horizontal_fov_deg / 2.0
        left_az = (self._facing_deg - half) % 360.0
        right_az = (self._facing_deg + half) % 360.0
        self.create_text(left, bottom + 18, text=f"{left_az:.0f}°", fill=muted, anchor="w")
        self.create_text((left + right) / 2, bottom + 18, text=f"Facing {self._facing_deg:.0f}°", fill=text, font=("Segoe UI", 10, "bold"))
        self.create_text(right, bottom + 18, text=f"{right_az:.0f}°", fill=muted, anchor="e")
        self.create_text(left + width / 2, top + 10, text="ZENITH", fill=muted, font=("Segoe UI", 8))
        self.create_text(left + width / 2, bottom - 10, text="HORIZON", fill=muted, font=("Segoe UI", 8))

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        selected = satellite.norad_id == self._selected_norad
        radius = 7 if selected else 5
        fill = "#fbbf24" if satellite.potentially_visible else "#60a5fa"
        outline = "#ffffff" if selected else fill
        tag = f"live-sat:{satellite.norad_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=2 if selected else 1,
            tags=(tag, "live-satellite"),
        )
        self.create_text(x + 9, y - 9, text=satellite.name, fill="#dbeafe", anchor="sw", font=("Segoe UI", 8), tags=(tag,))
        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _select(self, satellite: SkySatellite) -> None:
        self._selected_norad = satellite.norad_id
        self.redraw()
        if self._on_select is not None:
            self._on_select(satellite)
