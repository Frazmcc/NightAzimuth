from __future__ import annotations

import tkinter as tk
from typing import Callable

from .aircraft import AircraftSightline, aircraft_sightline, project_aircraft_position
from .directional_cloud_hud import DirectionalCloudHudFinderView
from .live_view import project_live_view


class AircraftHudFinderView(DirectionalCloudHudFinderView):
    """Directional sky finder with a selectable, source-labelled aircraft layer."""

    MAX_LABELS = 12
    PREDICTION_SECONDS = 30.0

    def __init__(
        self,
        *args: object,
        on_aircraft_select: Callable[[AircraftSightline], None] | None = None,
        **kwargs: object,
    ) -> None:
        self._aircraft: tuple[AircraftSightline, ...] = ()
        self._aircraft_future: dict[str, AircraftSightline] = {}
        self._show_aircraft = False
        self._selected_aircraft_hex: str | None = None
        self._on_aircraft_select = on_aircraft_select
        self._aircraft_observer: tuple[float, float, float] | None = None
        super().__init__(*args, **kwargs)

    @property
    def aircraft_in_view_count(self) -> int:
        return sum(1 for item in self._aircraft if self._projection(item).visible)

    def focus_low_sky(self, maximum_elevation_deg: float = 20.0) -> None:
        """Zoom the vertical view to the low sky without altering true aircraft elevation."""
        maximum = max(5.0, min(60.0, float(maximum_elevation_deg)))
        self._minimum_elevation_deg = 0.0
        self._maximum_elevation_deg = maximum
        self.redraw()

    def set_aircraft(
        self,
        aircraft: tuple[AircraftSightline, ...],
        *,
        observer_latitude: float,
        observer_longitude: float,
        observer_altitude_m: float,
    ) -> None:
        self._aircraft = tuple(sorted(aircraft, key=lambda item: item.slant_range_km))
        self._aircraft_observer = (
            float(observer_latitude),
            float(observer_longitude),
            float(observer_altitude_m),
        )
        self._aircraft_future = {}
        for item in self._aircraft:
            future_position = project_aircraft_position(item.aircraft, self.PREDICTION_SECONDS)
            if future_position is item.aircraft:
                continue
            self._aircraft_future[item.aircraft.hex_id] = aircraft_sightline(
                future_position,
                observer_latitude=self._aircraft_observer[0],
                observer_longitude=self._aircraft_observer[1],
                observer_altitude_m=self._aircraft_observer[2],
            )
        if self._selected_aircraft_hex not in {item.aircraft.hex_id for item in aircraft}:
            self._selected_aircraft_hex = None
        self.redraw()

    def clear_aircraft(self) -> None:
        self._aircraft = ()
        self._aircraft_future = {}
        self._selected_aircraft_hex = None
        self.redraw()

    def set_aircraft_enabled(self, enabled: bool) -> None:
        self._show_aircraft = bool(enabled)
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        if not self._show_aircraft:
            return
        left, top, right, bottom = self._plot_bounds()
        width = max(right - left, 1.0)
        height = max(bottom - top, 1.0)
        visible = tuple(item for item in self._aircraft if self._projection(item).visible)
        for index, item in enumerate(visible):
            projection = self._projection(item)
            x = left + projection.x_fraction * width
            y = top + projection.y_fraction * height
            self._draw_aircraft_track(item, x, y, left, top, width, height)
            self._draw_aircraft_marker(item, x, y, show_label=index < self.MAX_LABELS)

        self.create_text(
            right - 6,
            bottom - 8,
            text=f"Aircraft in view: {len(visible)}",
            fill="#22d3ee",
            anchor="se",
            font=("Segoe UI", 8, "bold"),
            tags=("aircraft-count",),
        )

    def _projection(self, item: AircraftSightline):
        return project_live_view(
            item.azimuth_deg,
            item.elevation_deg,
            self.facing_deg,
            self.horizontal_fov_deg,
            minimum_elevation_deg=self.minimum_elevation_deg,
            maximum_elevation_deg=self.maximum_elevation_deg,
        )

    def _draw_aircraft_track(
        self,
        item: AircraftSightline,
        x: float,
        y: float,
        left: float,
        top: float,
        width: float,
        height: float,
    ) -> None:
        future = self._aircraft_future.get(item.aircraft.hex_id)
        if future is None:
            return
        projection = self._projection(future)
        if not projection.visible:
            return
        end_x = left + projection.x_fraction * width
        end_y = top + projection.y_fraction * height
        self.create_line(
            x,
            y,
            end_x,
            end_y,
            fill="#67e8f9",
            width=2 if item.aircraft.hex_id == self._selected_aircraft_hex else 1,
            dash=(3, 3),
            arrow=tk.LAST,
            arrowshape=(7, 8, 3),
            tags=("aircraft-track", f"aircraft:{item.aircraft.hex_id}"),
        )

    def _draw_aircraft_marker(
        self,
        item: AircraftSightline,
        x: float,
        y: float,
        *,
        show_label: bool,
    ) -> None:
        selected = item.aircraft.hex_id == self._selected_aircraft_hex
        radius = 7 if selected else 5
        tag = f"aircraft:{item.aircraft.hex_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#22d3ee",
            outline="#ffffff" if selected else "#083344",
            width=2 if selected else 1,
            tags=("aircraft-marker", tag),
        )
        if show_label or selected:
            altitude_ft = item.aircraft.altitude_m / 0.3048
            label = f"{item.aircraft.callsign}  {altitude_ft:,.0f} ft"
            self.create_text(
                x + radius + 4,
                y - radius - 2,
                text=label,
                fill="#a5f3fc",
                anchor="sw",
                font=("Segoe UI", 8, "bold" if selected else "normal"),
                tags=("aircraft-label", tag),
            )
        self.tag_bind(tag, "<Button-1>", lambda _event, hex_id=item.aircraft.hex_id: self._select_aircraft(hex_id))

    def _select_aircraft(self, hex_id: str) -> None:
        selected = next((item for item in self._aircraft if item.aircraft.hex_id == hex_id), None)
        if selected is None:
            return
        self._selected_aircraft_hex = hex_id
        self.redraw()
        if self._on_aircraft_select is not None:
            self._on_aircraft_select(selected)

    def _on_pan_start(self, event: tk.Event) -> None:
        if self.find_withtag("current"):
            if any(tag.startswith("aircraft:") for tag in self.gettags("current")):
                self._pan_start = None
                self._pan_origin = None
                return
        super()._on_pan_start(event)
