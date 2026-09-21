from __future__ import annotations

from collections.abc import Callable
import math
import time
import tkinter as tk

from .aircraft_live import SkyAircraft
from .aircraft_motion import AircraftPositionState
from .aircraft_squawk import SquawkPriority
from .live_view import project_live_view, signed_angular_difference
from .twilight_hud_finder_view import TwilightSmoothHudFinderView


def interpolated_aircraft_sky_position(
    aircraft: SkyAircraft,
    elapsed_seconds: float,
) -> tuple[float, float]:
    """Interpolate along a short aircraft sky projection for smooth rendering."""
    points = aircraft.future_track
    if not points:
        return aircraft.azimuth_deg, aircraft.elevation_deg
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


def centred_elevation_window(
    elevation_deg: float,
    minimum_elevation_deg: float,
    maximum_elevation_deg: float,
) -> tuple[float, float]:
    """Centre a vertical Live-Finder window on an elevation while staying within 0..90°."""
    span = max(5.0, min(90.0, maximum_elevation_deg - minimum_elevation_deg))
    minimum = elevation_deg - span / 2.0
    maximum = minimum + span
    if minimum < 0.0:
        maximum -= minimum
        minimum = 0.0
    if maximum > 90.0:
        minimum -= maximum - 90.0
        maximum = 90.0
    return max(0.0, minimum), min(90.0, maximum)


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
        self._aircraft_animation_started = time.monotonic()
        self._drawn_aircraft_positions: dict[str, tuple[float, float]] = {}
        super().__init__(*args, **kwargs)

    @property
    def selected_icao24(self) -> str | None:
        return self._selected_icao24

    @property
    def visible_aircraft_count(self) -> int:
        return len(self._aircraft_in_current_view()) if self._show_aircraft else 0

    def aircraft_in_current_view(self) -> list[SkyAircraft]:
        """Return aircraft currently inside the displayed azimuth/elevation window."""
        return list(self._aircraft_in_current_view()) if self._show_aircraft else []

    def set_aircraft(self, aircraft: list[SkyAircraft]) -> None:
        self._aircraft = list(aircraft)
        self._aircraft_animation_started = time.monotonic()
        if self._selected_icao24 not in {item.icao24 for item in aircraft}:
            self._selected_icao24 = None
        self._redraw_aircraft_only()

    def set_show_aircraft(self, show: bool) -> None:
        self._show_aircraft = bool(show)
        self._redraw_aircraft_only()

    def select_aircraft(self, icao24: str | None) -> None:
        self._selected_icao24 = None if icao24 is None else icao24.strip().lower()
        self._redraw_aircraft_only()

    def centre_on_aircraft(self, icao24: str | None = None) -> bool:
        """Centre the finder on a selected/current aircraft using its smooth projected position."""
        target_id = (icao24 or self._selected_icao24 or "").strip().lower()
        if not target_id:
            return False
        aircraft = next((item for item in self._aircraft if item.icao24 == target_id), None)
        if aircraft is None:
            return False

        elapsed = max(0.0, time.monotonic() - self._aircraft_animation_started)
        azimuth, elevation = interpolated_aircraft_sky_position(aircraft, elapsed)
        self._facing_deg = azimuth % 360.0
        minimum, maximum = centred_elevation_window(
            elevation,
            self.minimum_elevation_deg,
            self.maximum_elevation_deg,
        )
        self._minimum_elevation_deg = minimum
        self._maximum_elevation_deg = maximum
        self._rebuild_display_satellites()
        return True

    def redraw(self) -> None:
        self._drawn_aircraft_positions = {}
        super().redraw()
        if self._show_aircraft:
            self._draw_aircraft_layer()

    def _animation_tick(self) -> None:
        self._animate_aircraft()
        super()._animation_tick()

    def _on_pan_start(self, event: tk.Event) -> None:
        if self.find_withtag("current"):
            tags = self.gettags("current")
            if any(tag.startswith("live-aircraft:") for tag in tags):
                self._pan_start = None
                self._pan_origin = None
                return
        super()._on_pan_start(event)

    def _redraw_aircraft_only(self) -> None:
        self.delete("live-aircraft")
        self.delete("aircraft-track")
        self.delete("aircraft-summary")
        self._drawn_aircraft_positions = {}
        if self._show_aircraft:
            self._draw_aircraft_layer()

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
        label_ids.update(
            item.icao24
            for item in contacts
            if item.military
            or (item.squawk_alert is not None and item.squawk_alert.highlighted)
        )
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
            self._drawn_aircraft_positions[aircraft.icao24] = (x, y)

        special_count = sum(1 for item in contacts if item.squawk_alert is not None)
        military_count = sum(1 for item in contacts if item.military)
        summary = f"Aircraft in view: {len(contacts)}"
        if special_count:
            summary += f"  •  special: {special_count}"
        if military_count:
            summary += f"  •  military: {military_count}"
        self.create_text(
            right - 6,
            top + 28,
            text=summary,
            fill="#67e8f9",
            anchor="ne",
            font=("Segoe UI", 8, "bold"),
            tags=("aircraft-summary",),
        )

    def _animate_aircraft(self) -> None:
        if not self._show_aircraft or not self._aircraft:
            return
        elapsed = max(0.0, time.monotonic() - self._aircraft_animation_started)
        left, top, right, bottom = self._plot_bounds()
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)

        for aircraft in self._aircraft:
            old_position = self._drawn_aircraft_positions.get(aircraft.icao24)
            if old_position is None or not aircraft.future_track:
                continue
            azimuth, elevation = interpolated_aircraft_sky_position(aircraft, elapsed)
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
            new_x = left + projection.x_fraction * plot_width
            new_y = top + projection.y_fraction * plot_height
            dx = new_x - old_position[0]
            dy = new_y - old_position[1]
            if dx or dy:
                self.move(f"live-aircraft:{aircraft.icao24}", dx, dy)
                self._drawn_aircraft_positions[aircraft.icao24] = (new_x, new_y)

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
                fill=_aircraft_display_colour(aircraft),
                width=2 if aircraft.squawk_alert is not None or aircraft.military else 1,
                dash=(3, 4),
                tags=(f"live-aircraft:{aircraft.icao24}", "aircraft-track", "live-aircraft"),
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
        fill = _aircraft_display_colour(aircraft)
        highlighted = aircraft.military or (
            aircraft.squawk_alert is not None and aircraft.squawk_alert.highlighted
        )
        radius = 8.0 if highlighted else (7.0 if selected else 5.0)
        direction = self._aircraft_screen_direction(aircraft, x, y)
        polygon = _triangle_points(x, y, radius, direction)
        self.create_polygon(
            *polygon,
            fill=fill,
            outline="#ffffff" if selected or highlighted else fill,
            width=2 if selected or highlighted else 1,
            tags=(tag, "live-aircraft"),
        )

        if show_label:
            identity = aircraft.callsign or aircraft.icao24.upper()
            state_suffix = ""
            if aircraft.position_state == AircraftPositionState.EXTRAPOLATED:
                state_suffix = "  est"
            elif aircraft.position_state == AircraftPositionState.INTERPOLATED:
                state_suffix = "  interp"

            prefixes: list[str] = []
            if aircraft.squawk_alert is not None:
                prefixes.append(f"{aircraft.squawk_alert.label} [{aircraft.squawk_alert.code}]")
            if aircraft.military:
                military_text = "MILITARY"
                if aircraft.type_description:
                    military_text += f" — {aircraft.type_description}"
                elif aircraft.type_code:
                    military_text += f" — {aircraft.type_code}"
                prefixes.append(military_text)
            prefix = "  •  ".join(prefixes)
            if prefix:
                prefix += "  •  "

            label = (
                f"{prefix}{identity}{state_suffix}  "
                f"{aircraft.range_km:.1f} km  El {aircraft.elevation_deg:.0f}°"
            )
            self.create_text(
                x + 9,
                y - 9,
                text=label,
                fill=_aircraft_label_colour(aircraft),
                anchor="sw",
                font=("Segoe UI", 8, "bold" if selected or highlighted else "normal"),
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
        self._redraw_aircraft_only()
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


def _aircraft_display_colour(aircraft: SkyAircraft) -> str:
    alert = aircraft.squawk_alert
    if alert is not None:
        if alert.priority >= SquawkPriority.CRITICAL:
            return "#ef4444"
        if alert.priority >= SquawkPriority.IMPORTANT:
            return "#f97316"
        return "#a855f7"
    if aircraft.military:
        return "#3b82f6"
    return _aircraft_colour(aircraft.position_state)


def _aircraft_label_colour(aircraft: SkyAircraft) -> str:
    alert = aircraft.squawk_alert
    if alert is not None:
        if alert.priority >= SquawkPriority.CRITICAL:
            return "#fecaca"
        if alert.priority >= SquawkPriority.IMPORTANT:
            return "#fed7aa"
        return "#e9d5ff"
    if aircraft.military:
        return "#bfdbfe"
    return "#a5f3fc"
