from __future__ import annotations

from collections.abc import Callable
import math
import tkinter as tk

from .aircraft_live import SkyAircraft
from .aircraft_motion import AircraftPositionState
from .live_view import project_live_view
from .twilight_hud_finder_view import TwilightSmoothHudFinderView


class AircraftTwilightFinderView(TwilightSmoothHudFinderView):
    """Twilight finder with an optional observer-centred aircraft overlay."""

    MAX_AUTOMATIC_LABELS = 12

    def __init__(
        self,
        *args: object,
        on_aircraft_select: Callable[[SkyAircraft], None] | None = None,
        **kwargs: object,
    ) -> None:
        self._aircraft: list[SkyAircraft] = []
        self._selected_icao24: str | None = None
        self._show_aircraft = True
        self._on_aircraft_select = on_aircraft_select
        super().__init__(*args, **kwargs)

    @property
    def selected_icao24(self) -> str | None:
        return self._selected_icao24

    @property
    def visible_aircraft_count(self) -> int:
        return len(self._aircraft_in_current_view()) if self._show_aircraft else 0

    def set_aircraft(self, aircraft: list[SkyAircraft]) -> None:
        self._aircraft = list(aircraft)
        if self._selected_icao24 not in {item.icao24 for item in aircraft}:
            self._selected_icao24 = None
        self.redraw()

    def set_show_aircraft(self, show: bool) -> None:
        self._show_aircraft = bool(show)
        self.redraw()

    def select_aircraft(self, icao24: str | None) -> None:
        self._selected_icao24 = None if icao24 is None else icao24.strip().lower()
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        if self._show_aircraft:
            self._draw_aircraft_layer()

    def _on_pan_start(self, event: tk.Event) -> None:
        if self.find_withtag("current"):
            tags = self.gettags("current")
            if any(tag.startswith("live-aircraft:") for tag in tags):
                self._pan_start = None
                self._pan_origin = None
                return
        super()._on_pan_start(event)

    def _aircraft_in_current_view(self) -> list[SkyAircraft]:
        result: list[SkyAircraft] = []
        for aircraft in self._aircraft:
            projection = project_live_view(
                aircraft.azimuth_deg,
                aircraft.elevation_deg,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            if projection.visible:
                result.append(aircraft)
        return result

    def _draw_aircraft_layer(self) -> None:
        contacts = self._aircraft_in_current_view()
        if not contacts:
            return

        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        selected = self._selected_icao24

        label_ids = {item.icao24 for item in contacts[: self.MAX_AUTOMATIC_LABELS]}
        if selected is not None:
            label_ids.add(selected)

        for aircraft in contacts:
            projection = project_live_view(
                aircraft.azimuth_deg,
                aircraft.elevation_deg,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            x = left + projection.x_fraction * plot_width
            y = top + projection.y_fraction * plot_height
            self._draw_aircraft_track(aircraft, left, top, plot_width, plot_height)
            self._draw_aircraft(
                aircraft,
                x,
                y,
                show_label=aircraft.icao24 in label_ids,
            )

        self.create_text(
            right - 6,
            top + 28,
            text=f"Aircraft in view: {len(contacts)}",
            fill="#67e8f9",
            anchor="ne",
            font=("Segoe UI", 8, "bold"),
            tags=("aircraft-summary",),
        )

    def _draw_aircraft_track(
        self,
        aircraft: SkyAircraft,
        left: float,
        top: float,
        plot_width: float,
        plot_height: float,
    ) -> None:
        if len(aircraft.future_track) < 2:
            return

        points: list[float] = []
        for point in aircraft.future_track:
            projection = project_live_view(
                point.azimuth_deg,
                point.elevation_deg,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            if not projection.visible:
                continue
            points.extend(
                (
                    left + projection.x_fraction * plot_width,
                    top + projection.y_fraction * plot_height,
                )
            )

        if len(points) >= 4:
            self.create_line(
                *points,
                fill="#22d3ee",
                width=1,
                dash=(3, 4),
                tags=(f"live-aircraft:{aircraft.icao24}", "aircraft-track"),
            )

    def _draw_aircraft(
        self,
        aircraft: SkyAircraft,
        x: float,
        y: float,
        *,
        show_label: bool,
    ) -> None:
        selected = aircraft.icao24 == self._selected_icao24
        tag = f"live-aircraft:{aircraft.icao24}"
        fill = _aircraft_colour(aircraft.position_state)
        radius = 7.0 if selected else 5.0
        direction = self._aircraft_screen_direction(aircraft, x, y)
        polygon = _triangle_points(x, y, radius, direction)
        self.create_polygon(
            *polygon,
            fill=fill,
            outline="#ffffff" if selected else fill,
            width=2 if selected else 1,
            tags=(tag, "live-aircraft"),
        )

        if show_label:
            identity = aircraft.callsign or aircraft.icao24.upper()
            state_suffix = ""
            if aircraft.position_state == AircraftPositionState.EXTRAPOLATED:
                state_suffix = "  est"
            elif aircraft.position_state == AircraftPositionState.INTERPOLATED:
                state_suffix = "  interp"
            label = (
                f"{identity}{state_suffix}  "
                f"{aircraft.range_km:.1f} km  El {aircraft.elevation_deg:.0f}°"
            )
            self.create_text(
                x + 8,
                y - 8,
                text=label,
                fill="#a5f3fc",
                anchor="sw",
                font=("Segoe UI", 8, "bold" if selected else "normal"),
                tags=(tag, "live-aircraft"),
            )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=aircraft: self._select_aircraft(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _aircraft_screen_direction(
        self,
        aircraft: SkyAircraft,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        if len(aircraft.future_track) < 2:
            return 0.0, -1.0
        point = aircraft.future_track[1]
        projection = project_live_view(
            point.azimuth_deg,
            point.elevation_deg,
            self.facing_deg,
            self.horizontal_fov_deg,
            minimum_elevation_deg=self.minimum_elevation_deg,
            maximum_elevation_deg=self.maximum_elevation_deg,
        )
        if not projection.visible:
            return 0.0, -1.0
        left, top, right, bottom = self._plot_bounds()
        next_x = left + projection.x_fraction * max(right - left, 1.0)
        next_y = top + projection.y_fraction * max(bottom - top, 1.0)
        dx = next_x - x
        dy = next_y - y
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return 0.0, -1.0
        return dx / length, dy / length

    def _select_aircraft(self, aircraft: SkyAircraft) -> None:
        self._selected_icao24 = aircraft.icao24
        self.redraw()
        if self._on_aircraft_select is not None:
            self._on_aircraft_select(aircraft)


def _triangle_points(
    x: float,
    y: float,
    radius: float,
    direction: tuple[float, float],
) -> tuple[float, ...]:
    dx, dy = direction
    side_x, side_y = -dy, dx
    tip_x = x + dx * radius
    tip_y = y + dy * radius
    back_x = x - dx * radius * 0.65
    back_y = y - dy * radius * 0.65
    return (
        tip_x,
        tip_y,
        back_x + side_x * radius * 0.65,
        back_y + side_y * radius * 0.65,
        back_x - side_x * radius * 0.65,
        back_y - side_y * radius * 0.65,
    )


def _aircraft_colour(state: AircraftPositionState) -> str:
    if state == AircraftPositionState.EXTRAPOLATED:
        return "#fbbf24"
    if state == AircraftPositionState.STALE:
        return "#94a3b8"
    return "#22d3ee"
