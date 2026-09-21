from __future__ import annotations

import time

from .hud_finder_view import apparent_angular_speed_deg_s
from .sky_map import SkySatellite
from .smooth_hud_finder_view import interpolated_satellite_position
from .stage20_airport_live_view import Stage20AirportLiveSkyView
from .stage20_live_sky_view import ISS_NORAD_ID
from .stage20_perceptual_projection import project_perceptual_live_view


class Stage20RealtimeSatelliteLiveSkyView(Stage20AirportLiveSkyView):
    """Continuously animated satellite layer with tracks rebased to 'now'."""

    REALTIME_TRACK_REFRESH_SECONDS = 0.20
    MAX_AUTOMATIC_TRACKS = 10

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._last_realtime_track_refresh = 0.0
        super().__init__(*args, **kwargs)

    def set_satellites(self, satellites: list[SkySatellite]) -> None:
        """Swap Stage 20 satellite data without falling back to legacy filtering.

        Stage 20 intentionally renders every satellite in the current view. The
        historical SmoothHudFinderView update path re-selected only naked-eye
        candidates when predicted tracks arrived, which made smooth tracking
        appear to stop or disappear. Keep the Stage 20 display contract here.
        """
        incoming = list(satellites)
        if self._all_satellites and self._satellites and not any(item.future_track for item in incoming):
            # A refresh publishes current positions before its background track
            # prediction completes. Hold the current smooth scene until the
            # complete tracked snapshot is ready.
            return

        self._all_satellites = incoming
        if self._selected_norad not in {item.norad_id for item in incoming}:
            self._selected_norad = None
        self._animation_started = time.monotonic()
        self._rebuild_display_satellites()

    def _draw_track(self, satellite: object, left: float, top: float, right: float, bottom: float) -> None:
        # The historical path renderer is anchored to the prediction epoch. Stage
        # 20 draws paths separately and continuously rebases them to the current
        # interpolated position, so a future track never appears left behind.
        return

    def _animation_tick(self) -> None:
        super()._animation_tick()
        now = time.monotonic()
        if now - self._last_realtime_track_refresh >= self.REALTIME_TRACK_REFRESH_SECONDS:
            self._last_realtime_track_refresh = now
            self._redraw_realtime_satellite_tracks(now)

    def _realtime_track_ids(self) -> set[str]:
        tracked = [item for item in self._satellites if len(item.future_track) >= 2]
        tracked.sort(
            key=lambda item: (
                -apparent_angular_speed_deg_s(item),
                -item.elevation_deg,
                item.range_km,
            )
        )
        ids = {item.norad_id for item in tracked[: self.MAX_AUTOMATIC_TRACKS]}
        ids.add(ISS_NORAD_ID)
        if self.selected_norad:
            ids.add(self.selected_norad)
        return ids

    def _redraw_realtime_satellite_tracks(self, now_monotonic: float) -> None:
        self.delete("realtime-satellite-track")
        if not self._satellites:
            return

        elapsed = max(0.0, now_monotonic - self._animation_started)
        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        wanted = self._realtime_track_ids()

        for satellite in self._satellites:
            if satellite.norad_id not in wanted or len(satellite.future_track) < 2:
                continue
            points = _remaining_track_points(satellite, elapsed)
            projected: list[tuple[float, float]] = []
            for azimuth, elevation in points:
                projection = project_perceptual_live_view(
                    azimuth,
                    elevation,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=self.minimum_elevation_deg,
                    maximum_elevation_deg=self.maximum_elevation_deg,
                )
                if not projection.visible:
                    if len(projected) >= 2:
                        self._draw_realtime_track_segment(satellite, projected)
                    projected = []
                    continue
                projected.append(
                    (
                        left + projection.x_fraction * plot_width,
                        top + projection.y_fraction * plot_height,
                    )
                )
            if len(projected) >= 2:
                self._draw_realtime_track_segment(satellite, projected)

        self.tag_lower("realtime-satellite-track", "live-satellite")

    def _draw_realtime_track_segment(self, satellite: object, points: list[tuple[float, float]]) -> None:
        norad_id = str(getattr(satellite, "norad_id", ""))
        selected = norad_id == self.selected_norad
        is_iss = norad_id == ISS_NORAD_ID
        colour = "#facc15" if is_iss else "#f472b6"
        flattened = [coordinate for point in points for coordinate in point]
        self.create_line(
            *flattened,
            fill=colour,
            width=2 if selected or is_iss else 1,
            dash=(3, 4),
            tags=("realtime-satellite-track", f"sat-track:{norad_id}"),
        )


def _remaining_track_points(satellite: object, elapsed_seconds: float) -> list[tuple[float, float]]:
    future_track = tuple(getattr(satellite, "future_track", ()))
    if len(future_track) < 2:
        return []
    current_azimuth, current_elevation = interpolated_satellite_position(satellite, elapsed_seconds)
    points: list[tuple[float, float]] = [(current_azimuth, current_elevation)]
    points.extend(
        (point.azimuth_deg, point.elevation_deg)
        for point in future_track
        if point.seconds_from_now > elapsed_seconds
    )
    return points
