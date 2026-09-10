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
    *,
    minimum_elevation_deg: float = 0.0,
    maximum_elevation_deg: float = 60.0,
) -> LiveProjection:
    """Project azimuth/elevation into a forward-looking rectangular sky view."""
    fov = max(5.0, min(180.0, horizontal_fov_deg))
    minimum = max(0.0, min(89.0, minimum_elevation_deg))
    maximum = max(minimum + 1.0, min(90.0, maximum_elevation_deg))
    half_fov = fov / 2.0
    offset = signed_angular_difference(azimuth_deg, facing_deg)
    visible = abs(offset) <= half_fov and minimum <= elevation_deg <= maximum
    x_fraction = 0.5 + offset / fov
    y_fraction = 1.0 - (elevation_deg - minimum) / (maximum - minimum)
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
        self._base_facing_deg = 0.0
        self._base_horizontal_fov_deg = 90.0
        self._facing_deg = 0.0
        self._horizontal_fov_deg = 90.0
        self._minimum_elevation_deg = 0.0
        self._maximum_elevation_deg = 60.0
        self._on_select = on_select
        self._drag_start: tuple[float, float] | None = None
        self._drag_rectangle: int | None = None

        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<MouseWheel>", self._on_mouse_wheel)
        self.bind("<ButtonPress-1>", self._on_drag_start, add="+")
        self.bind("<B1-Motion>", self._on_drag_motion, add="+")
        self.bind("<ButtonRelease-1>", self._on_drag_end, add="+")

    @property
    def facing_deg(self) -> float:
        return self._facing_deg

    @property
    def horizontal_fov_deg(self) -> float:
        return self._horizontal_fov_deg

    @property
    def minimum_elevation_deg(self) -> float:
        return self._minimum_elevation_deg

    @property
    def maximum_elevation_deg(self) -> float:
        return self._maximum_elevation_deg

    @property
    def selected_norad(self) -> str | None:
        return self._selected_norad

    def set_view(self, facing_deg: float, horizontal_fov_deg: float) -> None:
        self._base_facing_deg = facing_deg % 360.0
        self._base_horizontal_fov_deg = max(10.0, min(180.0, horizontal_fov_deg))
        self.reset_zoom()

    def zoom_in(self) -> None:
        self._zoom_about(0.7, 0.5, 0.5)

    def zoom_out(self) -> None:
        self._zoom_about(1.4, 0.5, 0.5)

    def reset_zoom(self) -> None:
        self._facing_deg = self._base_facing_deg
        self._horizontal_fov_deg = self._base_horizontal_fov_deg
        self._minimum_elevation_deg = 0.0
        self._maximum_elevation_deg = 60.0
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
        left, right = 52.0, width - 24.0
        top, bottom = 28.0, height - 54.0
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)

        self._draw_grid(left, top, right, bottom)

        visible_count = 0
        above_view_count = 0
        for satellite in self._satellites:
            if satellite.elevation_deg > self._maximum_elevation_deg:
                offset = signed_angular_difference(satellite.azimuth_deg, self._facing_deg)
                if abs(offset) <= self._horizontal_fov_deg / 2.0:
                    above_view_count += 1

            # Draw the short future path independently of the current marker.
            # This lets an object that is currently outside the selected view
            # show an incoming path if it will enter during the prediction window.
            self._draw_track(satellite, left, top, right, bottom)

            projection = project_live_view(
                satellite.azimuth_deg,
                satellite.elevation_deg,
                self._facing_deg,
                self._horizontal_fov_deg,
                minimum_elevation_deg=self._minimum_elevation_deg,
                maximum_elevation_deg=self._maximum_elevation_deg,
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

        if above_view_count:
            self.create_text(
                right,
                top - 10,
                text=f"{above_view_count} satellite{'s' if above_view_count != 1 else ''} above current elevation view",
                fill="#94a3b8",
                anchor="e",
                font=("Segoe UI", 8),
            )

    def _draw_track(
        self,
        satellite: SkySatellite,
        left: float,
        top: float,
        right: float,
        bottom: float,
    ) -> None:
        """Draw the visible portions of a satellite's short future path."""
        if len(satellite.future_track) < 2:
            return

        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        selected = satellite.norad_id == self._selected_norad
        colour = "#fbbf24" if satellite.potentially_visible else "#60a5fa"
        line_width = 2 if selected else 1
        segments: list[list[tuple[float, float, int]]] = []
        current_segment: list[tuple[float, float, int]] = []

        for point in satellite.future_track:
            projection = project_live_view(
                point.azimuth_deg,
                point.elevation_deg,
                self._facing_deg,
                self._horizontal_fov_deg,
                minimum_elevation_deg=self._minimum_elevation_deg,
                maximum_elevation_deg=self._maximum_elevation_deg,
            )
            if projection.visible:
                current_segment.append(
                    (
                        left + projection.x_fraction * plot_width,
                        top + projection.y_fraction * plot_height,
                        point.seconds_from_now,
                    )
                )
            elif current_segment:
                if len(current_segment) >= 2:
                    segments.append(current_segment)
                current_segment = []

        if len(current_segment) >= 2:
            segments.append(current_segment)

        for index, segment in enumerate(segments):
            flattened = [coordinate for x, y, _seconds in segment for coordinate in (x, y)]
            is_last = index == len(segments) - 1
            self.create_line(
                *flattened,
                fill=colour,
                width=line_width,
                dash=(4, 3),
                arrow=tk.LAST if is_last else tk.NONE,
                arrowshape=(8, 10, 4),
                tags=("projected-track",),
            )

        if selected and segments:
            end_x, end_y, duration = segments[-1][-1]
            if duration >= 60:
                label = f"+{duration // 60}m"
                if duration % 60:
                    label += f"{duration % 60:02d}s"
            else:
                label = f"+{duration}s"
            self.create_text(
                end_x + 6,
                end_y + 6,
                text=label,
                fill=colour,
                anchor="nw",
                font=("Segoe UI", 8, "bold"),
            )

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        grid = "#334155"
        text = "#dbeafe"
        muted = "#94a3b8"
        height = bottom - top

        self.create_rectangle(left, top, right, bottom, outline=grid, width=2)

        minimum = self._minimum_elevation_deg
        maximum = self._maximum_elevation_deg
        step = 10.0 if maximum - minimum >= 30.0 else 5.0
        first = int((minimum + step - 1) // step) * int(step)
        elevations = [minimum]
        value = float(first)
        while value < maximum:
            if value > minimum:
                elevations.append(value)
            value += step
        elevations.append(maximum)

        for elevation in elevations:
            fraction = (elevation - minimum) / (maximum - minimum)
            y = bottom - fraction * height
            self.create_line(left, y, right, y, fill=grid)
            self.create_text(
                left - 8,
                y,
                text=f"{elevation:.0f}°",
                fill=muted,
                anchor="e",
                font=("Segoe UI", 8),
            )

        half = self._horizontal_fov_deg / 2.0
        left_az = (self._facing_deg - half) % 360.0
        right_az = (self._facing_deg + half) % 360.0
        self.create_text(left, bottom + 18, text=f"{left_az:.0f}°", fill=muted, anchor="w")
        self.create_text(
            (left + right) / 2,
            bottom + 18,
            text=f"Facing {self._facing_deg:.0f}°",
            fill=text,
            font=("Segoe UI", 10, "bold"),
        )
        self.create_text(right, bottom + 18, text=f"{right_az:.0f}°", fill=muted, anchor="e")
        self.create_text(
            left,
            top - 10,
            text=(
                f"Elevation {minimum:.0f}–{maximum:.0f}°  |  "
                f"Horizontal FOV {self._horizontal_fov_deg:.0f}°"
            ),
            fill=muted,
            anchor="w",
            font=("Segoe UI", 8),
        )
        self.create_text((left + right) / 2, bottom - 10, text="HORIZON", fill=muted, font=("Segoe UI", 8))

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
        self.create_text(
            x + 9,
            y - 9,
            text=satellite.name,
            fill="#dbeafe",
            anchor="sw",
            font=("Segoe UI", 8),
            tags=(tag,),
        )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _select(self, satellite: SkySatellite) -> None:
        self._selected_norad = satellite.norad_id
        self.redraw()
        if self._on_select is not None:
            self._on_select(satellite)

    def _plot_bounds(self) -> tuple[float, float, float, float]:
        width = max(self.winfo_width(), 2)
        height = max(self.winfo_height(), 2)
        return 52.0, 28.0, width - 24.0, height - 54.0

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        left, top, right, bottom = self._plot_bounds()
        if not (left <= event.x <= right and top <= event.y <= bottom):
            return
        x_fraction = (event.x - left) / max(right - left, 1.0)
        y_fraction = (event.y - top) / max(bottom - top, 1.0)
        factor = 0.8 if event.delta > 0 else 1.25
        self._zoom_about(factor, x_fraction, y_fraction)

    def _zoom_about(self, factor: float, x_fraction: float, y_fraction: float) -> None:
        old_fov = self._horizontal_fov_deg
        new_fov = max(5.0, min(self._base_horizontal_fov_deg, old_fov * factor))
        horizontal_offset = (x_fraction - 0.5) * old_fov
        self._facing_deg = (self._facing_deg + horizontal_offset * (1.0 - factor)) % 360.0
        self._horizontal_fov_deg = new_fov

        old_min = self._minimum_elevation_deg
        old_max = self._maximum_elevation_deg
        old_span = old_max - old_min
        new_span = max(5.0, min(60.0, old_span * factor))
        cursor_elevation = old_max - y_fraction * old_span
        new_max = cursor_elevation + y_fraction * new_span
        new_min = new_max - new_span
        if new_min < 0.0:
            new_max -= new_min
            new_min = 0.0
        if new_max > 60.0:
            new_min -= new_max - 60.0
            new_max = 60.0
        self._minimum_elevation_deg = max(0.0, new_min)
        self._maximum_elevation_deg = min(60.0, new_max)
        self.redraw()

    def _on_drag_start(self, event: tk.Event) -> None:
        if self.find_withtag("current"):
            current_tags = self.gettags("current")
            if any(tag.startswith("live-sat:") for tag in current_tags):
                self._drag_start = None
                return
        left, top, right, bottom = self._plot_bounds()
        if left <= event.x <= right and top <= event.y <= bottom:
            self._drag_start = (float(event.x), float(event.y))

    def _on_drag_motion(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        if self._drag_rectangle is not None:
            self.delete(self._drag_rectangle)
        x0, y0 = self._drag_start
        self._drag_rectangle = self.create_rectangle(
            x0,
            y0,
            event.x,
            event.y,
            outline="#ffffff",
            dash=(4, 3),
            width=1,
        )

    def _on_drag_end(self, event: tk.Event) -> None:
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        x1, y1 = float(event.x), float(event.y)
        self._drag_start = None
        if self._drag_rectangle is not None:
            self.delete(self._drag_rectangle)
            self._drag_rectangle = None

        if abs(x1 - x0) < 12 or abs(y1 - y0) < 12:
            return

        left, top, right, bottom = self._plot_bounds()
        x0 = max(left, min(right, x0))
        x1 = max(left, min(right, x1))
        y0 = max(top, min(bottom, y0))
        y1 = max(top, min(bottom, y1))

        low_x, high_x = sorted((x0, x1))
        low_y, high_y = sorted((y0, y1))
        width = max(right - left, 1.0)
        height = max(bottom - top, 1.0)

        old_fov = self._horizontal_fov_deg
        left_offset = ((low_x - left) / width - 0.5) * old_fov
        right_offset = ((high_x - left) / width - 0.5) * old_fov
        self._facing_deg = (self._facing_deg + (left_offset + right_offset) / 2.0) % 360.0
        self._horizontal_fov_deg = max(5.0, right_offset - left_offset)

        old_min = self._minimum_elevation_deg
        old_max = self._maximum_elevation_deg
        old_span = old_max - old_min
        selected_max = old_max - ((low_y - top) / height) * old_span
        selected_min = old_max - ((high_y - top) / height) * old_span
        if selected_max - selected_min >= 5.0:
            self._minimum_elevation_deg = max(0.0, selected_min)
            self._maximum_elevation_deg = min(60.0, selected_max)
        self.redraw()