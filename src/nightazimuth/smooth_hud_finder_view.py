from __future__ import annotations

import time
import tkinter as tk

from .hud_finder_view import HudFinderView, select_finder_satellites
from .live_view import project_live_view, signed_angular_difference
from .sky_map import SkySatellite


def interpolated_satellite_position(
    satellite: SkySatellite,
    elapsed_seconds: float,
) -> tuple[float, float]:
    """Interpolate a satellite along its predicted track for smooth display motion."""
    points = satellite.future_track
    if not points:
        return satellite.azimuth_deg, satellite.elevation_deg
    if elapsed_seconds <= points[0].seconds_from_now:
        return points[0].azimuth_deg, points[0].elevation_deg
    if elapsed_seconds >= points[-1].seconds_from_now:
        return points[-1].azimuth_deg, points[-1].elevation_deg

    previous = points[0]
    for following in points[1:]:
        if elapsed_seconds <= following.seconds_from_now:
            span = following.seconds_from_now - previous.seconds_from_now
            if span <= 0:
                return following.azimuth_deg, following.elevation_deg
            fraction = (elapsed_seconds - previous.seconds_from_now) / span
            azimuth_delta = signed_angular_difference(
                following.azimuth_deg,
                previous.azimuth_deg,
            )
            azimuth = (previous.azimuth_deg + azimuth_delta * fraction) % 360.0
            elevation = previous.elevation_deg + (
                following.elevation_deg - previous.elevation_deg
            ) * fraction
            return azimuth, elevation
        previous = following

    return points[-1].azimuth_deg, points[-1].elevation_deg


class SmoothHudFinderView(HudFinderView):
    """HUD finder with smoothly animated satellite markers."""

    ANIMATION_INTERVAL_MS = 50  # 20 frames per second

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._animation_started = time.monotonic()
        self._drawn_satellite_positions: dict[str, tuple[float, float]] = {}
        self._animation_job: str | None = None
        super().__init__(*args, **kwargs)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._schedule_animation()

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        """Swap refreshed orbital data without blanking/repainting an unchanged Live view.

        A full redraw is still required when the displayed candidate set changes.
        For the normal periodic refresh, where the same satellites remain selected,
        keep the existing canvas items in place and simply replace the backing tracks.
        The next 20 fps animation tick then moves them onto the refreshed prediction.
        """
        incoming = list(satellites)
        if not self._all_satellites or not self._satellites:
            self._animation_started = time.monotonic()
            super().set_satellites(incoming)
            return

        old_ids = tuple(satellite.norad_id for satellite in self._satellites)
        self._all_satellites = incoming
        if self._selected_norad not in {satellite.norad_id for satellite in incoming}:
            self._selected_norad = None

        in_view = self._satellites_in_current_view()
        refreshed = select_finder_satellites(
            in_view,
            selected_norad=None,
            limit=self.DEFAULT_CANDIDATE_LIMIT,
            show_all=self._show_all_tracked,
        )
        if self._selected_norad is not None and all(
            satellite.norad_id != self._selected_norad for satellite in refreshed
        ):
            selected = next(
                (satellite for satellite in incoming if satellite.norad_id == self._selected_norad),
                None,
            )
            if selected is not None:
                refreshed.append(selected)

        new_ids = tuple(satellite.norad_id for satellite in refreshed)
        self._satellites = refreshed
        self._animation_started = time.monotonic()

        if new_ids != old_ids:
            self.redraw()

    def redraw(self) -> None:
        self._drawn_satellite_positions = {}
        super().redraw()

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        super()._draw_satellite(satellite, x, y)
        self._drawn_satellite_positions[satellite.norad_id] = (x, y)

    def _schedule_animation(self) -> None:
        if self._animation_job is None and self.winfo_exists():
            self._animation_job = self.after(self.ANIMATION_INTERVAL_MS, self._animation_tick)

    def _animation_tick(self) -> None:
        self._animation_job = None
        if not self.winfo_exists():
            return

        elapsed = max(0.0, time.monotonic() - self._animation_started)
        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)

        satellites = self._satellites
        if self._show_all_tracked and self.selected_norad is not None:
            satellites = [
                satellite
                for satellite in satellites
                if satellite.norad_id == self.selected_norad
            ]

        for satellite in satellites:
            if not satellite.future_track:
                continue
            azimuth, elevation = interpolated_satellite_position(satellite, elapsed)
            projection = project_live_view(
                azimuth,
                elevation,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            if not projection.visible:
                continue

            old_position = self._drawn_satellite_positions.get(satellite.norad_id)
            if old_position is None:
                continue
            new_x = left + projection.x_fraction * plot_width
            new_y = top + projection.y_fraction * plot_height
            dx = new_x - old_position[0]
            dy = new_y - old_position[1]
            if dx or dy:
                self.move(f"live-sat:{satellite.norad_id}", dx, dy)
                self._drawn_satellite_positions[satellite.norad_id] = (new_x, new_y)

        self._schedule_animation()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if self._animation_job is not None:
            try:
                self.after_cancel(self._animation_job)
            except tk.TclError:
                pass
            self._animation_job = None
